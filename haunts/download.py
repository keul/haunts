from googleapiclient.discovery import build
from datetime import datetime, timedelta

from .ini import get
from .credentials import get_credentials
from .spreadsheet import get_calendars
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


def get_events(events_service, calendar_id, date):
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
    return events


def extract_events(config_dir, sheet):
    calendar_credentials = get_credentials(
        config_dir, CALENDAR_SCOPES, "calendars-token.json"
    )
    spreadsheeet_credentials = get_credentials(
        config_dir, SPREADSHEET_SCOPES, "sheets-token.json"
    )
    calendar_service = build("calendar", "v3", credentials=calendar_credentials)
    spreadsheet_service = build("sheets", "v4", credentials=spreadsheeet_credentials)

    date_to_check = datetime(
        year=2023, month=5, day=21
    ).date()  # Replace with the desired date

    events_service = calendar_service.events()
    sheet_service = spreadsheet_service.spreadsheets()

    configued_calendars = get_calendars(sheet_service, ignore_alias=True)
    print(configued_calendars)

    all_events = []
    for calendar_id in configued_calendars.values():
        print(f"checking {calendar_id}")
        events = get_events(events_service, calendar_id, date_to_check)
        all_events.extend(filter_my_event(events))

    for event in all_events:
        print(event)
        event_summary = event.get("summary", "No summary")
        start_time = event["start"].get("dateTime", event["start"].get("date"))
        end_time = event["end"].get("dateTime", event["end"].get("date"))
        print(f"Summary: {event_summary}")
        print(f"Start Time: {start_time}")
        print(f"End Time: {end_time}")
        print("---")
