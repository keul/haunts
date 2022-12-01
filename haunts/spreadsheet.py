import datetime
import string
import sys
import time
import click
from colorama import Back, Fore, Style
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from . import LOGGER
from . import actions
from .credentials import get_credentials
from .calendars import ORIGIN_TIME, create_event, delete_event, formatDate
from .ini import get

# If scopes are modified, delete the sheets-token file
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_col(row, index):
    try:
        return row[index]
    except IndexError:
        return None


def get_headers(sheet, month, indexes=False):
    """Scan headers of a month and returns a structure that assign headers names to indexes"""
    selected_month = (
        sheet.values()
        .get(spreadsheetId=get("CONTROLLER_SHEET_DOCUMENT_ID"), range=f"{month}!A1:ZZ1")
        .execute()
    )
    values = selected_month["values"][0]
    if indexes:
        return {k: values.index(k) for k in values}
    return {k: string.ascii_lowercase.upper()[values.index(k)] for k in values}


def sync_events(config_dir, sheet, data, calendars, days, month, projects=[]):
    """Create an event when action column is empty."""
    headers = get_headers(sheet, month)
    headers_id = get_headers(sheet, month, indexes=True)
    last_to_time = None
    last_date = None
    warn_lines = []

    for y, row in enumerate(data["values"]):
        action = ""
        try:
            action = row[headers_id["Action"]]
        except IndexError:
            # We have no action defined
            pass

        project = get_col(row, headers_id["Project"])

        if action == actions.IGNORE:
            continue

        current_date = get_col(row, headers_id["Date"])
        if not current_date:
            LOGGER.debug("No date found, skipping")
            continue

        if projects and project not in projects:
            continue

        date = ORIGIN_TIME + datetime.timedelta(days=current_date)
        default_start_time = (
            get_col(row, headers_id["Start time"])
            if headers_id.get("Start time") and get_col(row, headers_id["Start time"])
            else None
        )

        # In case we changed day, let's restart from START_TIME
        if current_date != last_date:
            last_to_time = None
        last_date = current_date

        # short circuit for date filters
        skip = len(days) > 0
        for d in days:
            if date.date() == d.date():
                skip = False
                break
        if skip:
            continue

        calendar = None

        try:
            calendar = calendars[project]
        except KeyError:
            click.echo(
                Back.YELLOW
                + Fore.BLACK
                + f"Cannot find a calendar id associated to project \"{get_col(row, headers_id['Project'])}\" at line {y+2}"
                + Style.RESET_ALL
            )
            warn_lines.append(y)
            continue

        if action == actions.DELETE:
            delete_event(
                config_dir=config_dir,
                calendar=calendar,
                event_id=get_col(row, headers_id["Event id"]),
            )
            click.echo(
                f'Deleted event "{get_col(row, headers_id["Activity"])}" in date {date.strftime("%d/%m")} from calendar {project}'
            )
            request = sheet.values().batchClear(
                spreadsheetId=get("CONTROLLER_SHEET_DOCUMENT_ID"),
                body={
                    "ranges": [
                        f"{month}!{headers['Event id']}{y + 2}",
                        f"{month}!{headers['Link']}{y + 2}",
                        f"{month}!{headers['Action']}{y + 2}",
                    ],
                },
            )

            try:
                request.execute()
            except HttpError as err:
                if err.status_code == 429:
                    click.echo("Too many requests")
                    click.echo(err.error_details)
                    click.echo("haunts will now pause for a while ⏲…")
                    time.sleep(60)
                    click.echo("Retrying…")
                    request.execute()
                else:
                    raise

            continue

        if action:
            # There's something in the action cell, but not recognized
            click.echo(
                Back.YELLOW
                + Fore.BLACK
                + f'Unknown action "{action}" at line {y + 2}. Ignoring…'
                + Style.RESET_ALL
            )
            warn_lines.append(y)
            continue

        event = create_event(
            config_dir=config_dir,
            calendar=calendar,
            date=date,
            summary=get_col(row, headers_id["Activity"]),
            details=get_col(row, headers_id["Details"]),
            length=get_col(row, headers_id["Spent"]),
            from_time=default_start_time or last_to_time,
        )
        last_to_time = event["next_slot"]

        request = sheet.values().batchUpdate(
            spreadsheetId=get("CONTROLLER_SHEET_DOCUMENT_ID"),
            body={
                "valueInputOption": "USER_ENTERED",
                "data": [
                    # Put the action to actions.IGNORE, in this way it will not be processed again
                    {
                        "range": f"{month}!{headers['Action']}{y + 2}",
                        "values": [[actions.IGNORE]],
                    },
                    # Save the event id, required to interact with the event in future
                    {
                        "range": f"{month}!{headers['Event id']}{y + 2}",
                        "values": [[event["id"]]],
                    },
                    # Quick link to the event on the calendar
                    {
                        "range": f"{month}!{headers['Link']}{y + 2}",
                        "values": [[f"=HYPERLINK(\"{event['link']}\";\"open\")"]],
                    },
                ],
            },
        )

        try:
            request.execute()
        except HttpError as err:
            if err.status_code == 429:
                click.echo("Too many requests")
                click.echo(err.error_details)
                click.echo("haunts will now pause for a while ⏲…")
                time.sleep(60)
                click.echo("Retrying…")
                request.execute()
            else:
                raise
    click.echo("Done!")

    if warn_lines:
        click.echo("")
        click.echo(
            Back.YELLOW
            + Fore.BLACK
            + f"⚠️ ⚠️ ⚠️ - There are {len(warn_lines)} lines with warnings. Please check them. ⚠️ ⚠️ ⚠️ "
            + Style.RESET_ALL
        )


def get_calendars(sheet):
    RANGE = f"{get('CONTROLLER_SHEET_NAME', 'config')}!A2:B"
    calendars = (
        sheet.values()
        .get(spreadsheetId=get("CONTROLLER_SHEET_DOCUMENT_ID"), range=RANGE)
        .execute()
    )
    values = calendars.get("values", [])
    return {alias: id for [id, alias] in values}


def sync_report(config_dir, month, days=[], projects=[]):
    """Open a sheet, analyze it and populate calendars with new events."""
    # The ID and range of the controller timesheet
    creds = get_credentials(config_dir, SCOPES, "sheets-token.json")
    service = build("sheets", "v4", credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()

    click.echo("Started calendars synchronization")

    try:
        document_id = get("CONTROLLER_SHEET_DOCUMENT_ID")
    except KeyError:
        click.echo(
            "A value for CONTROLLER_SHEET_DOCUMENT_ID is required but "
            "is not specified in your ini file"
        )
        sys.exit(1)

    try:
        data = (
            sheet.values()
            .get(
                spreadsheetId=document_id,
                range=f"{month}!A2:ZZ",
                valueRenderOption="UNFORMATTED_VALUE",
            )
            .execute()
        )
    except HttpError as err:
        click.echo(
            Back.RED + f'Sheet "{month}" not found or not accessible.' + Style.RESET_ALL
        )
        click.echo(err.error_details)
        sys.exit(1)

    calendars = get_calendars(sheet)
    sync_events(
        config_dir, sheet, data, calendars, days=days, month=month, projects=projects
    )
