"""Console script for haunts."""
import datetime
import os
import sys
from pathlib import Path

import click

from .ini import create_default, init

from .calendars import init as init_calendars
from .spreadsheet import sync_report

config_dir = Path(os.path.expanduser("~/.haunts"))

if not config_dir.is_dir():
    click.echo(f"Creating config directory at {config_dir.resolve()}")
    config_dir.mkdir()
    click.echo("…created")


config = Path(os.path.expanduser(f"{config_dir.resolve()}/haunts.ini"))
if not config.is_file():
    create_default(config)
    click.echo(f"Manage you settings at {config.resolve()} and try again")
    sys.exit(0)
else:
    init(config)


@click.command()
@click.argument("sheet")
@click.option(
    "--day",
    "-d",
    multiple=True,
    help='day filter in format "YYYY-MM-DD". Can be provided multiple times.',
)
def main(sheet, day=[]):
    """
    Sync events from a Google Sheet to your Google Calendar.
    """
    click.echo("Started calendars synchronization")
    init_calendars(config_dir)
    sync_report(
        config_dir,
        sheet,
        days=[datetime.datetime.strptime(d, "%Y-%m-%d") for d in day],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
