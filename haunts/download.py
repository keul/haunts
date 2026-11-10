from dateutil import tz
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import click
from colorama import Back, Fore, Style

from .ini import get
from .credentials import get_credentials
from . import proton
from .spreadsheet import (
    append_line,
    get_calendars_names,
    get_calendars_by_id,
    get_calendars,
    get_calendar_col_values,
)
from .spreadsheet import SCOPES as SPREADSHEET_SCOPES
from .calendars import SCOPES as CALENDAR_SCOPES

GOOGLE = "google"
PROTON = "proton"
SERVICES = (GOOGLE, PROTON)
SERVICE_NAMES = {GOOGLE: "Google", PROTON: "Proton"}


class ConfigurationError(Exception):
    """Raised when the configuration does not allow to read events."""


def filter_my_events(events):
    """
    Take a list of Google Calendar events and returns events created by USER_EMAIL
    or events that have USER_EMAIL in the attendees list.

    Exclude events where the user has declined the invitation: events answered with "maybe"
    are read, to be reviewed later in the sheet.
    """
    USER_EMAIL = get("USER_EMAIL")
    if USER_EMAIL is None:
        raise KeyError("USER_EMAIL not set in configuration")
    for event in events:
        if event.get("creator", {}).get("email") == USER_EMAIL and event.get("attendees", []) == []:
            yield event
        elif USER_EMAIL in [
            attendee.get("email")
            for attendee in event.get("attendees", [])
            if attendee.get("responseStatus") in ["accepted", "tentative", "needsAction"]
        ]:
            yield event


def format_hours(duration):
    """Format a timedelta as hours, like "1 hour" or "1.5 hours"."""
    hours = round(duration.total_seconds() / 3600, 2)
    value = f"{hours:g}"
    return f"{value} hour" if hours == 1 else f"{value} hours"


def describe_timing(event, start_time, duration):
    """Describe when an event happens, for log messages."""
    if "date" in event["start"]:
        # All-day event
        days = duration.days
        return "full day" if days <= 1 else f"full day ({days} days)"
    return f"at {start_time} (lasts {format_hours(duration)})"


def get_events_at(events_service, calendar_id, date):
    """Get all events from a calendar in a specific date."""
    start_datetime = datetime.combine(date, datetime.min.time())
    end_datetime = (
        datetime.combine(date, datetime.min.time()) + timedelta(days=1) - timedelta(seconds=1)
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
    return [{**e, "calendar_id": calendar_id, "source": "Google"} for e in events]


def get_proton_events(
    proton_calendars, date, already_added_events, organizer_projects=None, google_uids=None
):
    """Get events from Proton Calendar in a specific date.

    Events in a calendar not configured in the config sheet are assigned to the project of
    their organizer, when the organizer is a calendar in the config sheet (like Google
    calendars inviting you), otherwise to the catch-all calendar.
    Calendars of ignored kinds (like holidays) are skipped.

    Events already read from Google Calendar (same iCalendar UID) are skipped.
    """
    organizer_projects = organizer_projects or {}
    google_uids = google_uids or set()
    events = []
    ignored_calendars = None
    for event in proton.get_events_at(date):
        if event["htmlLink"] in already_added_events:
            continue
        if event["uid"] and event["uid"] in google_uids:
            click.echo(
                f"Event {event['summary']} (from Proton) is a duplicate of a Google event. "
                "Skipping…"
            )
            continue
        if event["calendar_id"] not in proton_calendars:
            if ignored_calendars is None:
                ignored_calendars = proton.get_calendar_ids(proton.IGNORED_CALENDAR_KINDS)
            if event["proton_calendar_id"] in ignored_calendars:
                continue
            event["calendar_id"] = proton.PROTON_CATCH_ALL
            project = organizer_projects.get(event["organizer"])
            if project:
                event["project"] = project
                event["source"] = "Proton, by organizer"
        already_added_events.add(event["htmlLink"])
        events.append(event)
    return events


def get_read_services(skip=()):
    """Calendar services to read events from.

    Services are taken from READ_FROM_SERVICES configuration option (default: all of them),
    minus the ones in skip.
    Proton is used only when configured (see PROTON_CLI): if READ_FROM_SERVICES is not set it is
    silently ignored, otherwise an error is raised.
    """
    raw = get("READ_FROM_SERVICES", "").strip()
    services = [s.strip().lower() for s in (raw or ",".join(SERVICES)).split(",") if s.strip()]
    unknown = [s for s in services if s not in SERVICES]
    if unknown:
        raise ConfigurationError(
            f"Unknown service(s) in READ_FROM_SERVICES: {', '.join(unknown)}. "
            f"Allowed values are: {', '.join(SERVICES)}"
        )
    services = [s for s in SERVICES if s in services and s not in skip]
    if PROTON in services and not proton.is_enabled():
        if raw:
            raise ConfigurationError(
                "READ_FROM_SERVICES includes proton, but PROTON_CLI is not set in haunts.ini"
            )
        services.remove(PROTON)
    if PROTON in services and not proton.get_my_emails():
        raise ConfigurationError(
            "Set PROTON_EMAIL (or USER_EMAIL) in haunts.ini to read from Proton Calendar"
        )
    if not services:
        raise ConfigurationError("No calendar service left to read events from")
    return services


def extract_events(config_dir, sheet, day, services=(GOOGLE,)):
    """Public module entry point.

    Extract events from calendar services (Google Calendar, Proton Calendar)
    and copy them to proper Google Sheet.
    """
    spreadsheeet_credentials = get_credentials(config_dir, SPREADSHEET_SCOPES, "sheets-token.json")
    spreadsheet_service = build("sheets", "v4", credentials=spreadsheeet_credentials)
    sheet_service = spreadsheet_service.spreadsheets()

    date_to_check = datetime.strptime(day, "%Y-%m-%d").date()  # Replace with the desired date

    click.echo(
        f"Checking your calendars at {day} "
        f"(reading from: {', '.join(SERVICE_NAMES[s] for s in services)})…"
    )

    if PROTON in services:
        # Fail early if proton-cli is not available, warn if it's too old
        warning = proton.check_version()
        if warning:
            click.echo(Back.YELLOW + Fore.BLACK + warning + Style.RESET_ALL)

    configured_calendars = get_calendars(sheet_service, ignore_alias=True, use_read_col=True)
    proton_calendars = {c for c in configured_calendars.values() if proton.is_proton_calendar(c)}
    if proton_calendars and PROTON not in services:
        click.echo(
            Back.YELLOW
            + Fore.BLACK
            + "Proton calendars found in the config sheet are ignored, "
            + "as Proton Calendar is not read"
            + Style.RESET_ALL
        )

    all_events = []
    if GOOGLE in services:
        calendar_credentials = get_credentials(config_dir, CALENDAR_SCOPES, "calendars-token.json")
        events_service = build("calendar", "v3", credentials=calendar_credentials).events()
        google_calendars = [
            c for c in configured_calendars.values() if not proton.is_proton_calendar(c)
        ]
        google_calendars.append(get("USER_EMAIL"))
        # Get "my events" from all configured calendars in the selected date
        already_added_events = set()
        for calendar_id in google_calendars:
            events = get_events_at(events_service, calendar_id, date_to_check)
            new_events = [
                e for e in filter_my_events(events) if e["id"] not in already_added_events
            ]
            already_added_events.update([e["id"] for e in new_events])
            all_events.extend(new_events)

    if PROTON in services:
        click.echo("Checking your Proton calendars…")
        # Errors are propagated: nothing has been written on the sheet yet
        all_events.extend(
            get_proton_events(
                proton_calendars,
                date_to_check,
                set(),
                organizer_projects=get_calendars_by_id(sheet_service),
                google_uids={e["iCalUID"] for e in all_events if e.get("iCalUID")},
            )
        )

    # Sort events by start time
    all_events.sort(key=lambda x: x["start"].get("dateTime", x["start"].get("date")))

    # Get calendar configurations
    calendar_names = get_calendars_names(sheet_service, flat=False)
    # Forcibly add the user's calendar to the list
    if GOOGLE in services:
        calendar_names[get("USER_EMAIL")] = {"alias": "???", "is_linked": False}
    # Proton events are always copied to Google Calendar later by `sync`, like linked calendars
    calendar_names[proton.PROTON_CATCH_ALL] = {"alias": "???", "is_linked": True}

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
        project = event.get("project") or calendar_names[event["calendar_id"]]["alias"]
        is_linked = calendar_names[event["calendar_id"]]["is_linked"]

        start_date = datetime.fromisoformat(start).date()
        start_time = datetime.fromisoformat(start).time()
        duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
        event_id = event["id"] if not is_linked else ""
        if event_id and event_id in all_sheet_events:
            click.echo(
                Back.YELLOW
                + Fore.BLACK
                + (
                    f"Event {event_summary} ({event_id}, from {event.get('source', 'Google')}) "
                    f"already present in the sheet. Skipping…"
                )
                + Style.RESET_ALL
            )
            continue
        event_link = event.get("htmlLink", "")
        if event_link and event_link in all_sheet_event_urls:
            click.echo(
                Back.YELLOW
                + Fore.BLACK
                + (
                    f"A link to event {event_summary} "
                    f"({event_link}, from {event.get('source', 'Google')}) "
                    f"already present in the sheet. "
                    f"Skipping…"
                )
                + Style.RESET_ALL
            )
            continue
        click.echo(
            f"Adding new event {event_summary} ({project} - from {event.get('source', 'Google')}) "
            f"{describe_timing(event, start_time, duration)} to selected sheet"
        )
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
