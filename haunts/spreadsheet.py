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
from .calendars import ORIGIN_TIME, create_event, delete_event
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


def sync_events(
    config_dir, sheet, data, calendars, days, month, projects=[], allowed_actions=[]
):
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

        if action == actions.IGNORE or action == actions.IGNORE_ALL:
            continue

        if (
            # We want to filter by Action value and current action is not in the provided set
            (
                allowed_actions
                and action not in allowed_actions
                and "empty" not in allowed_actions
            )
            or
            # …or action is not empty and we want to act on empty Action lines only
            (action and "empty" in allowed_actions)
        ):
            LOGGER.debug(
                f"Action {action} at line {y+1}, not in allowed actions {allowed_actions}"
            )
            continue

        current_date = get_col(row, headers_id["Date"])
        if not current_date:
            LOGGER.debug(f"No date found at line {y+1}, skipping")
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
                + (
                    f"Cannot find a calendar id associated to project "
                    f"\"{get_col(row, headers_id['Project'])}\" at line {y+2}"
                )
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
                f'Deleted event "{get_col(row, headers_id["Activity"])}" in date '
                f'{date.strftime("%d/%m")} from calendar {project}'
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
            + (
                f"⚠️ ⚠️ ⚠️ - There are {len(warn_lines)} lines with warnings. "
                "Please check them. ⚠️ ⚠️ ⚠️ "
            )
            + Style.RESET_ALL
        )


def get_calendars(sheet, ignore_alias=False, use_read_col=False):
    """In case ignore_alias is true, only the first occurence of a calendar is returned.

    In case use_read_col is True, the preferred calendar id is taken from "read_from" column
    """
    RANGE = f"{get('CONTROLLER_SHEET_NAME', 'config')}!A2:C"
    calendars = (
        sheet.values()
        .get(spreadsheetId=get("CONTROLLER_SHEET_DOCUMENT_ID"), range=RANGE)
        .execute()
    )
    values = calendars.get("values", [])
    configured_calendars = {}
    for cols in values:
        if not use_read_col:
            try:
                id, alias = cols
            except ValueError:
                # not required alias column
                id, alias, _ = cols
            read_from = None
        else:
            try:
                id, alias, read_from = cols
            except ValueError:
                # no linked_id
                id, alias = cols
                read_from = None
        if ignore_alias and (
            id in configured_calendars or read_from in configured_calendars
        ):
            continue
        configured_calendars[alias] = read_from or id
    return configured_calendars


def get_calendar_col_values(sheet, month, col_name):
    """Get all events ids for a month."""
    headers_ids = get_headers(sheet, month, indexes=True)
    col_of_interest = headers_ids.get(col_name)
    # transform a zero.based index to a capital letter
    col_of_interest = string.ascii_uppercase[col_of_interest]
    RANGE = f"{month}!{col_of_interest}2:{col_of_interest}"
    events = (
        sheet.values()
        .get(spreadsheetId=get("CONTROLLER_SHEET_DOCUMENT_ID"), range=RANGE)
        .execute()
    )
    values = events.get("values", [])
    return [e[0] for e in values if e]


def get_calendars_names(sheet, flat=True):
    """Get all calendars names, giving precedence to alias defined in column "linked_calendar".

    If multiple aliases are found, the first one will be used
    """
    RANGE = f"{get('CONTROLLER_SHEET_NAME', 'config')}!A2:C"
    calendars = (
        sheet.values()
        .get(spreadsheetId=get("CONTROLLER_SHEET_DOCUMENT_ID"), range=RANGE)
        .execute()
    )
    values = calendars.get("values", [])
    names = {}
    for cols in values:
        try:
            id, alias, linked_id = cols
        except ValueError:
            # no linked_id
            id, alias = cols
            linked_id = None
        if names.get(linked_id) or (names.get(id) and not linked_id):
            continue
        names[linked_id or id] = (
            alias if flat else {"alias": alias, "is_linked": bool(linked_id)}
        )
    return names


def get_first_empty_line(sheet, month):
    """Get the first empty line in a month."""
    RANGE = f"{month}!A1:A"
    lines = (
        sheet.values()
        .get(spreadsheetId=get("CONTROLLER_SHEET_DOCUMENT_ID"), range=RANGE)
        .execute()
    )
    values = lines.get("values", [])
    return len(values) + 1


def format_duration(duration):
    """Given a timedelta duration, format is as a string.

    String format will be H,X or H if minutes are 0.
    X is the decimal part of the hour (30 minutes are 0.5 hours, etc)
    """
    hours = duration.total_seconds() / 3600
    if hours % 1 == 0:
        return str(int(hours))
    return str(hours).replace(".", ",")


def append_line(
    sheet,
    month,
    date_col,
    time_col,
    project_col,
    activity_col,
    event_id_col=None,
    link_col="",
    details_col="",
    action_col="",
    duration_col=None,
):
    """Append a new line at the end of a sheet."""
    next_av_line = get_first_empty_line(sheet, month)
    headers_id = get_headers(sheet, month, indexes=True)
    # Now write a new line at position next_av_line
    RANGE = f"{month}!A{next_av_line}:ZZ{next_av_line}"
    values_line = []
    formatted_time_col = time_col.strftime("%H:%M") if time_col else ""
    formatted_duration_col = format_duration(duration_col) if duration_col else ""
    full_day = formatted_time_col == "00:00" and formatted_duration_col == "24"
    for key, index in headers_id.items():
        if key == "Date":
            values_line.append(date_col.strftime("%d/%m/%Y"))
        elif key == "Start time":
            values_line.append(formatted_time_col if not full_day else "")
        elif key == "Project":
            values_line.append(project_col)
        elif key == "Activity":
            values_line.append(activity_col)
        elif key == "Details":
            values_line.append(details_col)
        elif key == "Event id":
            values_line.append(event_id_col)
        elif key == "Link":
            values_line.append(link_col)
        elif key == "Action":
            values_line.append(action_col)
        elif key == "Spent":
            values_line.append(formatted_duration_col if not full_day else "")
        else:
            values_line.append("")

    request = sheet.values().batchUpdate(
        spreadsheetId=get("CONTROLLER_SHEET_DOCUMENT_ID"),
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [
                {
                    "range": RANGE,
                    "values": [values_line],
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


def sync_report(config_dir, month, days=[], projects=[], allowed_actions=[]):
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
        config_dir,
        sheet,
        data,
        calendars,
        days=days,
        month=month,
        projects=projects,
        allowed_actions=allowed_actions,
    )
