"""Report module."""

import click
from googleapiclient.discovery import build


def report(config_dir, sheet, project=[]):
    """Open a sheet, analyze it and extract stats."""
    # The ID and range of the controller timesheet
    get_credentials(config_dir)
    service = build("sheets", "v4", credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()

    click.echo("Started calendars synchronization")
