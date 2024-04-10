"""Report module."""

import datetime
import numbers
import sys

import click
from colorama import Back, Fore, Style
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tabulate import SEPARATING_LINE, tabulate

from . import LOGGER
from . import actions
from .calendars import LOCAL_TIMEZONE
from .credentials import get_credentials
from .ini import get
from .spreadsheet import ORIGIN_TIME, get_col, get_headers

# If scopes are modified, delete the sheets-token file
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def adjust_full_day(proj_stats):
    """Calculate the value of a full day event, taking into account other events."""
    value = 0
    count = 0
    total_overtime = 0
    for entry_stats in proj_stats["projects"].values():
        count += entry_stats["total"]
        total_overtime += entry_stats["overtime"]
    value = int(get("WORKING_HOURS", 8)) - count + total_overtime
    # now properly adjust the full day value
    for entry_stats in proj_stats["projects"].values():
        if entry_stats["full_day"]:
            entry_stats["total"] += value
            break


def print_report(report, days=[], projects=[], overtime=False):
    rows = []
    gran_total = 0
    # Tranform report to be tabulate compatible
    headers = ["Date", "Project", "Total"]
    for date, proj_stats in report.items():
        if proj_stats.get("have_full_day", False):
            adjust_full_day(proj_stats)
        for project, stat in proj_stats["projects"].items():
            overtime_value = stat["overtime"]
            if overtime and overtime_value:
                # Just want to count the overtime amount
                total = overtime_value
            else:
                total = stat["total"]

            if (
                # not filtering by project, or project is in the list
                (not projects or project in projects)
                # not filtering by days, or day is in the list
                and (not days or date in days)
                # not filtering by overtime, or this is an overtime entry
                and (not overtime or overtime_value)
            ):
                rows.append([date, project, total])
                gran_total += total

    if not rows:
        click.echo("No data to display.")
        return
    else:
        rows.extend([SEPARATING_LINE, ["", "", gran_total]])
    click.echo(tabulate(rows, headers=headers, tablefmt="simple"))


def create_report(sheet, sheet_name, data, overtime=False):
    """Create a time consumption report from a sheet."""
    headers_id = get_headers(sheet, sheet_name, indexes=True)
    overtime_from = get("OVERTIME_FROM", default=False)

    dates = {}

    if overtime and not get("OVERTIME_FROM"):
        click.echo(
            Back.RED
            + "Cannot filter by --overtime: OVERTIME_FROM is not set."
            + Style.RESET_ALL
        )
        sys.exit(1)

    for y, row in enumerate(data["values"]):

        action = ""
        try:
            action = row[headers_id["Action"]]
        except IndexError:
            # We have no action defined
            pass

        if action == actions.IGNORE_ALL:
            continue

        current_date = get_col(row, headers_id["Date"])
        if not current_date:
            LOGGER.debug("No date found, skipping")
            continue

        date = (ORIGIN_TIME + datetime.timedelta(days=current_date)).date()
        start_time = (
            get_col(row, headers_id["Start time"])
            if headers_id.get("Start time") and get_col(row, headers_id["Start time"])
            else None
        )

        in_overtime = False
        if start_time and overtime_from:
            start = datetime.datetime.strptime(
                f"{date.strftime('%Y-%m-%d')}T{start_time}:00{LOCAL_TIMEZONE}",
                "%Y-%m-%dT%H:%M:%S%z",
            )
            overtime = datetime.datetime.strptime(
                f"{date.strftime('%Y-%m-%d')}T{overtime_from}:00{LOCAL_TIMEZONE}",
                "%Y-%m-%dT%H:%M:%S%z",
            )
            if start >= overtime:
                in_overtime = True

        project = get_col(row, headers_id["Project"])
        date_stats = dates.get(
            str(date),
            {
                "projects": {},
                "have_full_day": False,
            },
        )
        prog_stats = date_stats["projects"].get(
            project,
            {
                "total": 0,
                "overtime": 0,
                "full_day": False,
            },
        )
        spent = get_col(row, headers_id["Spent"])

        # We have a value of spent hours in this event
        if isinstance(spent, numbers.Number):
            prog_stats["total"] += spent
            if in_overtime:
                prog_stats["overtime"] += spent
        elif isinstance(spent, str) and not spent:
            # Check: we have multiple full days in the same day! haunts is not supporting this
            if date_stats["have_full_day"]:
                click.echo(
                    Back.YELLOW
                    + Fore.BLACK
                    + f"There are multiple full days in the same day: {str(date)}"
                    + Style.RESET_ALL
                )
            else:
                date_stats["have_full_day"] = True
                prog_stats["full_day"] = True

        date_stats["projects"][project] = prog_stats
        dates[str(date)] = date_stats

    return dates


def report(config_dir, sheet_name, days=[], projects=[], overtime=False):
    """Open a sheet, analyze it and extract stats."""
    # The ID and range of the controller timesheet
    creds = get_credentials(config_dir, SCOPES, "sheets-token.json")
    service = build("sheets", "v4", credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()

    click.echo("Collecting report…")

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
                range=f"{sheet_name}!A2:ZZ",
                valueRenderOption="UNFORMATTED_VALUE",
            )
            .execute()
        )
    except HttpError as err:
        click.echo(
            Back.RED
            + f'Sheet "{sheet_name}" not found or not accessible.'
            + Style.RESET_ALL
        )
        click.echo(err.error_details)
        sys.exit(1)

    report = create_report(
        sheet=sheet, sheet_name=sheet_name, data=data, overtime=overtime
    )

    click.echo("")
    print_report(report, days=days, projects=projects, overtime=overtime)
    click.echo("")
