"""Report module."""

import sys
import click
import datetime
import numbers
from googleapiclient.discovery import build
from colorama import Back, Fore, Style
from googleapiclient.errors import HttpError
from tabulate import tabulate, SEPARATING_LINE

from . import LOGGER
from .credentials import get_credentials
from .spreadsheet import get_headers, get_col, ORIGIN_TIME
from .calendars import LOCAL_TIMEZONE
from .ini import get

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


def print_report(report, days=[], projects=[]):
    rows = []
    gran_total = 0
    # Tranform report to be tabulate compatible
    headers = ["Date", "Project", "Total"]
    for date, proj_stats in report.items():
        if proj_stats.get("have_full_day", False):
            adjust_full_day(proj_stats)
        for project, stat in proj_stats["projects"].items():
            total = stat["total"]
            if (not projects or project in projects) and (not days or date in days):
                rows.append([date, project, total])
                gran_total += total

    if not rows:
        click.echo("No data to display.")
        return
    else:
        rows.extend([SEPARATING_LINE, ["", "", gran_total]])
    click.echo(tabulate(rows, headers=headers, tablefmt="simple"))


def create_report(sheet, sheet_name, data):
    """Create a time consumption report from a sheet."""
    headers_id = get_headers(sheet, sheet_name, indexes=True)
    overtime_from = get("OVERTIME_FROM", default=False)

    dates = {}

    for y, row in enumerate(data["values"]):

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
                f"%Y-%m-%dT%H:%M:%S%z",
            )
            overtime = datetime.datetime.strptime(
                f"{date.strftime('%Y-%m-%d')}T{overtime_from}:00{LOCAL_TIMEZONE}",
                f"%Y-%m-%dT%H:%M:%S%z",
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
        elif type(spent) == str and not spent:
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


def report(config_dir, sheet_name, days=[], projects=[]):
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

    report = create_report(sheet=sheet, sheet_name=sheet_name, data=data)

    click.echo("")
    print_report(report, days=days, projects=projects)
    click.echo("")
