#!/usr/bin/env python

"""Console script for haunts."""
import datetime
import os
import sys
from pathlib import Path
from importlib.metadata import version
import click

from .ini import create_default, init
from .calendars import init as init_calendars
from .spreadsheet import sync_report
from .report import report


@click.command()
@click.argument("sheet", required=False)
@click.option(
    "--day",
    "-d",
    multiple=True,
    help='day filter in format "YYYY-MM-DD". Can be provided multiple times.',
)
@click.option(
    "--config",
    "-c",
    "run_configuration",
    help="configure haunts working folder and .ini file.",
    is_flag=True,
    show_default=True,
    default=False,
)
@click.option(
    "--action",
    "-a",
    type=click.Choice(["sync", "report"], case_sensitive=False),
    help="select which action to execute.",
    show_default=True,
    default="sync",
)
@click.option(
    "--project",
    "-p",
    multiple=True,
    help="project filter. Used to limit action to specific projects. Can be provided multiple times.",
    default=[],
)
@click.option(
    "--version",
    "-v",
    "show_version",
    help="show version and exit.",
    is_flag=True,
)
def main(
    sheet=None,
    day=[],
    run_configuration=False,
    action="sync",
    project=[],
    show_version=False,
):
    """
    Sync events from a Google Sheet to your Google Calendar.
    """

    if show_version:
        click.echo(version("haunts"))
        sys.exit(0)

    # config phase
    config_dir = Path(os.path.expanduser("~/.haunts"))

    if not run_configuration and not config_dir.is_dir():
        click.echo(
            f"Configuation directory at {config_dir.resolve()} not found. Use --config  to create it."
        )
        sys.exit(1)

    config = Path(os.path.expanduser(f"{config_dir.resolve()}/haunts.ini"))
    if not run_configuration and not config_dir.is_dir():
        click.echo(
            f"Configuation file at {config.resolve()} not found. Use --config to create it."
        )
        sys.exit(1)
    if run_configuration and not config_dir.is_dir():
        click.echo(f"Creating config directory at {config_dir.resolve()}")
        config_dir.mkdir()
        click.echo("…created")
        if not config.is_file():
            create_default(config)
            click.echo(
                f"Manage you settings at {config.resolve()} before running haunts again."
            )
            sys.exit(1)

    if not run_configuration and not sheet:
        click.echo(f"Argument SHEET is required if no '--config' flag is provided.")
        sys.exit(1)

    init(config)

    if run_configuration:
        click.echo("All done. You can now start using haunts.")
        sys.exit(0)

    init_calendars(config_dir)
    if action == "sync":
        sync_report(
            config_dir,
            sheet,
            days=[datetime.datetime.strptime(d, "%Y-%m-%d") for d in day],
            projects=project,
        )
    elif action == "report":
        report(
            config_dir,
            sheet,
            days=day,
            projects=project,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
