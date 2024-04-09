from googleapiclient.discovery import build
from datetime import datetime, timedelta
import click

from .ini import get
from .credentials import get_credentials
from .spreadsheet import (
    append_line,
    get_calendars_names,
    get_calendars,
)
from .spreadsheet import SCOPES as SPREADSHEET_SCOPES
from .calendars import SCOPES as CALENDAR_SCOPES


def filter_my_event(events):
    """
    Take a list of Google Calendar events and returns events created by USER_EMAIL
    or events that have USER_EMAIL in the attendees list.
    """
    USER_EMAIL = get("USER_EMAIL")
    if USER_EMAIL is None:
        raise KeyError("USER_EMAIL not set in configuration")
    for event in events:
        if event.get("creator", {}).get("email") == USER_EMAIL:
            yield event
        elif USER_EMAIL in [
            attendee.get("email") for attendee in event.get("attendees", [])
        ]:
            yield event


def get_events_at(events_service, calendar_id, date):
    """Get all events from a calendar in a specific date."""
    start_datetime = datetime.combine(date, datetime.min.time()).isoformat() + "Z"
    end_datetime = (
        datetime.combine(date, datetime.min.time())
        + timedelta(days=1)
        - timedelta(seconds=1)
    ).isoformat() + "Z"
    events_result = events_service.list(
        calendarId=calendar_id,
        timeMin=start_datetime,
        timeMax=end_datetime,
        singleEvents=True,
        orderBy="startTime",
        timeZone=get("TIMEZONE", "Etc/GMT"),
    ).execute()
    events = events_result.get("items", [])
    # Enrich events with calendar_id
    return [{**e, "calendar_id": calendar_id} for e in events]


def extract_events(config_dir, sheet, day):
    """Public module entry point.

    Extract events from Google Calendar and copy them to proper Google Sheet.
    """
    calendar_credentials = get_credentials(
        config_dir, CALENDAR_SCOPES, "calendars-token.json"
    )
    spreadsheeet_credentials = get_credentials(
        config_dir, SPREADSHEET_SCOPES, "sheets-token.json"
    )
    calendar_service = build("calendar", "v3", credentials=calendar_credentials)
    spreadsheet_service = build("sheets", "v4", credentials=spreadsheeet_credentials)

    date_to_check = datetime.strptime(
        day, "%Y-%m-%d"
    ).date()  # Replace with the desired date

    events_service = calendar_service.events()
    sheet_service = spreadsheet_service.spreadsheets()

    configured_calendars = get_calendars(
        sheet_service, ignore_alias=True, use_read_col=True
    )
    all_events = []
    # Get "my events" from all configured calendars in the selected date
    already_added_events = set()
    for calendar_id in configured_calendars.values():
        events = get_events_at(events_service, calendar_id, date_to_check)
        new_events = [
            e for e in filter_my_event(events) if e["id"] not in already_added_events
        ]
        already_added_events.update([e["id"] for e in new_events])
        all_events.extend(new_events)

    # Get calendar configurations
    calendar_names = get_calendars_names(sheet_service)

    # Main operation loop
    for event in all_events:
        event_summary = event.get("summary", "No summary")
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        project = calendar_names[event["calendar_id"]]

        start_date = datetime.fromisoformat(start).date()
        start_time = datetime.fromisoformat(start).time()
        duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
        click.echo(f"Adding new event {event_summary} ({project}) to selected sheet")
        append_line(
            sheet_service,
            sheet,
            date_col=start_date,
            time_col=start_time,
            duration_col=duration,
            project_col=project,
            activity_col=event_summary,
            details_col=event.get("description", ""),
            event_id_col=event["id"],
            link_col=event.get("htmlLink", ""),
            action_col="I",
        )
