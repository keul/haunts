from dateutil import tz
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import click
from colorama import Back, Fore, Style

from .ini import get
from .credentials import get_credentials
from .spreadsheet import (
    append_line,
    get_calendars_names,
    get_calendars,
    get_calendar_col_values,
)
from .spreadsheet import SCOPES as SPREADSHEET_SCOPES
from .calendars import SCOPES as CALENDAR_SCOPES


def filter_my_events(events):
    """
    Take a list of Google Calendar events and returns events created by USER_EMAIL
    or events that have USER_EMAIL in the attendees list.

    Exclude events where the user has declined the invitation.
    """
    USER_EMAIL = get("USER_EMAIL")
    if USER_EMAIL is None:
        raise KeyError("USER_EMAIL not set in configuration")
    for event in events:
        if (
            event.get("creator", {}).get("email") == USER_EMAIL
            and event.get("attendees", []) == []
        ):
            yield event
        elif USER_EMAIL in [
            attendee.get("email")
            for attendee in event.get("attendees", [])
            if attendee.get("responseStatus") in ["accepted", "needsAction"]
        ]:
            yield event


def get_events_at(events_service, calendar_id, date):
    """Get all events from a calendar in a specific date."""
    start_datetime = datetime.combine(date, datetime.min.time())
    end_datetime = (
        datetime.combine(date, datetime.min.time())
        + timedelta(days=1)
        - timedelta(seconds=1)
    )
    tz_obj = tz.gettz(get("TIMEZONE", "Etc/GMT"))
    start_datetime = start_datetime.replace(tzinfo=tz_obj)
    end_datetime = end_datetime.replace(tzinfo=tz_obj)
    events_result = events_service.list(
        calendarId=calendar_id,
        timeMin=start_datetime.isoformat(),
        timeMax=end_datetime.isoformat(),
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

    click.echo("Checking your calendars…")

    configured_calendars = get_calendars(
        sheet_service, ignore_alias=True, use_read_col=True
    )
    configured_calendars["???"] = get("USER_EMAIL")
    all_events = []
    # Get "my events" from all configured calendars in the selected date
    already_added_events = set()
    for calendar_id in configured_calendars.values():
        events = get_events_at(events_service, calendar_id, date_to_check)
        new_events = [
            e for e in filter_my_events(events) if e["id"] not in already_added_events
        ]
        already_added_events.update([e["id"] for e in new_events])
        all_events.extend(new_events)

    # Sort events by start time
    all_events.sort(key=lambda x: x["start"].get("dateTime", x["start"].get("date")))

    # Get calendar configurations
    calendar_names = get_calendars_names(sheet_service, flat=False)
    # Forcibly add the user's calendar to the list
    calendar_names[get("USER_EMAIL")] = {"alias": "???", "is_linked": False}

    # Get a list of all events ids already present in the sheet
    # This to prevent adding the same event multiple times
    all_sheet_events = get_calendar_col_values(sheet_service, sheet, "Event id")
    all_sheet_event_urls = get_calendar_col_values(sheet_service, sheet, "Link")

    click.echo(f"Start downloading events for day {day}")

    # Main operation loop
    for event in all_events:
        event_summary = event.get("summary", "No summary")
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        project = calendar_names[event["calendar_id"]]["alias"]
        is_linked = calendar_names[event["calendar_id"]]["is_linked"]

        start_date = datetime.fromisoformat(start).date()
        start_time = datetime.fromisoformat(start).time()
        duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
        event_id = event["id"] if not is_linked else ""
        if event_id and event_id in all_sheet_events:
            click.echo(
                Back.YELLOW
                + Fore.BLACK
                + (f"Event {event_summary} already present in the sheet. Skipping…")
                + Style.RESET_ALL
            )
            continue
        event_link = event.get("htmlLink", "")
        if event_link and event_link in all_sheet_event_urls:
            click.echo(
                Back.YELLOW
                + Fore.BLACK
                + (
                    f"A link to event {event_summary} already present in the sheet ({event_link}). "
                    f"Skipping…"
                )
                + Style.RESET_ALL
            )
            continue
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
            event_id_col=event_id,
            link_col=event_link,
            action_col="I" if not is_linked and project != "???" else "",
        )

    if not all_events:
        click.echo("No events found.")
    else:
        click.echo("Done!")
