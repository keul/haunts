import time
import datetime
import click
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
        f"{date.strftime('%Y-%m-%d')}T{from_time}:00{LOCAL_TIMEZONE}",
        f"%Y-%m-%dT%H:%M:%S%z",
    )

    startParams = None
    endParams = None
    haveLength = length is not None and type(length) is not str
    duration = None
    if haveLength:
        duration = float(length)
        delta = datetime.timedelta(hours=duration)
    else:
        delta = datetime.timedelta(hours=0)
    end = start + delta

    if haveLength:
        startParams = {
            "dateTime": start.isoformat(),
        }
        endParams = {
            "dateTime": end.isoformat(),
        }
    else:
        startParams = {
            "date": start.isoformat()[:10],
        }
        endParams = {
            "date": (end + datetime.timedelta(days=1)).isoformat()[:10],
        }

    event_body = {
        "summary": summary,
        "description": details,
        "start": startParams,
        "end": endParams,
    }

    def execute_creation():
        LOGGER.debug(calendar, date, summary, details, length, event_body, from_time)
        event = service.events().insert(calendarId=calendar, body=event_body).execute()
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
        click.echo(f"Missing id. Skipping…")
        return
    try:
        service.events().delete(calendarId=calendar, eventId=event_id).execute()
    except HttpError as err:
        if err.status_code == 410:
            click.echo(f"Event {event_id} already deleted")
