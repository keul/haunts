import time
import datetime
import click
from colorama import Back, Fore, Style
from dateutil import parser

from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

from . import LOGGER
from .ini import get
from .credentials import get_credentials

LOCAL_TIMEZONE = datetime.datetime.utcnow().astimezone().strftime("%z")
# Weird google spreadsheet date management
ORIGIN_TIME = datetime.datetime.strptime(
    f"1899-12-30T00:00:00{LOCAL_TIMEZONE}", "%Y-%m-%dT%H:%M:%S%z"
)
# If scopes are modified, delete the calendars-token file.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def formatDate(date, format):
    return parser.isoparse(date).strftime(format)


def init(config_dir):
    get_credentials(config_dir, SCOPES, "calendars-token.json")


def create_event(config_dir, calendar, date, summary, details, length, from_time=None):
    creds = get_credentials(config_dir, SCOPES, "calendars-token.json")
    service = build("calendar", "v3", credentials=creds)

    from_time = from_time or get("START_TIME", "09:00")
    start = datetime.datetime.strptime(
        f"{date.strftime('%Y-%m-%d')}T{from_time}:00Z",
        "%Y-%m-%dT%H:%M:%SZ",
    )

    startParams = None
    endParams = None
    haveLength = length is not None and not isinstance(length, str)
    duration = None
    if haveLength:
        duration = float(length)
        delta = datetime.timedelta(hours=duration)
    else:
        delta = datetime.timedelta(hours=0)
    end = start + delta

    if haveLength:
        # Event with a duration
        startParams = {
            "dateTime": start.isoformat(),
            "timeZone": get("TIMEZONE", "Etc/GMT"),
        }
        endParams = {
            "dateTime": end.isoformat(),
            "timeZone": get("TIMEZONE", "Etc/GMT"),
        }
    else:
        # Full day event
        startParams = {
            "date": start.isoformat()[:10],
            "timeZone": get("TIMEZONE", "Etc/GMT"),
        }
        endParams = {
            "date": (end + datetime.timedelta(days=1)).isoformat()[:10],
            "timeZone": get("TIMEZONE", "Etc/GMT"),
        }

    event_body = {
        "summary": summary,
        "description": details,
        "start": startParams,
        "end": endParams,
    }

    def execute_creation():
        LOGGER.debug(calendar, date, summary, details, length, event_body, from_time)
        try:
            event = (
                service.events().insert(calendarId=calendar, body=event_body).execute()
            )
        except HttpError as err:
            LOGGER.error(f"Cannot create the event: {err.status_code}")
            raise
        return event

    try:
        event = execute_creation()
    except HttpError as err:
        if err.status_code == 429:
            click.echo("Too many requests")
            click.echo(err.error_details)
            click.echo("haunts will now pause for a while ⏲…")
            time.sleep(60)
            click.echo("Retrying…")
            event = execute_creation()
        else:
            raise

    LOGGER.debug(event.items())
    if duration:
        click.echo(
            f'Created event "{summary}" from {formatDate(event["start"]["dateTime"], "%H:%M")} '
            f'to {formatDate(event["end"]["dateTime"], "%H:%M")} ({duration}h) '
            f'in date {formatDate(event["start"]["dateTime"], "%d/%m")} '
            f'on calendar {event["organizer"]["displayName"]}'
        )
    else:
        click.echo(
            f'Created event "{summary}" (full day) '
            f'in date {formatDate(event["start"]["date"], "%d/%m")} '
            f'on calendar {event["organizer"]["displayName"]}'
        )

    event_data = {
        "id": event["id"],
        "next_slot": end.strftime("%H:%M") if haveLength else from_time,
        "link": event["htmlLink"],
    }
    return event_data


def delete_event(config_dir, calendar, event_id):
    creds = get_credentials(config_dir, SCOPES, "calendars-token.json")
    service = build("calendar", "v3", credentials=creds)
    if not event_id:
        click.echo(
            Back.YELLOW
            + Fore.BLACK
            + "Missing event id, cannot delete"
            + Style.RESET_ALL
        )
        return
    try:
        service.events().delete(calendarId=calendar, eventId=event_id).execute()
    except HttpError as err:
        if err.status_code >= 400 and err.status_code < 500:
            click.echo(
                Back.YELLOW
                + Fore.BLACK
                + (
                    f"Event {event_id} not found (status code {err.status_code}). "
                    f"Maybe it's has been already deleted?"
                )
                + Style.RESET_ALL
            )
