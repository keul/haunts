import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from . import LOGGER
from .ini import get

LOCAL_TIMEZONE = datetime.datetime.utcnow().astimezone().strftime("%z")
# Weird google spreadsheet date management
ORIGIN_TIME = datetime.datetime.strptime(
    f"1899-12-30T00:00:00{LOCAL_TIMEZONE}", "%Y-%m-%dT%H:%M:%S%z"
)
# If modifying these scopes, delete the calendars-token file.
SCOPES = ["https://www.googleapis.com/auth/calendar"]
creds = None


def get_credentials(config_dir):
    global creds
    if creds is not None:
        return
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token = config_dir / "calendars-token.json"
    credentials = config_dir / "credentials.json"
    if token.is_file():
        creds = Credentials.from_authorized_user_file(token.resolve(), SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials.resolve(), SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token.resolve(), "w") as token:
            token.write(creds.to_json())


def init(config_dir):
    get_credentials(config_dir)


def create_event(config_dir, calendar, date, summary, details, length, from_time=None):
    get_credentials(config_dir)
    service = build("calendar", "v3", credentials=creds)

    from_time = from_time or get("START_TIME")
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

    event = {
        "summary": summary,
        "description": details,
        "start": startParams,
        "end": endParams,
    }

    LOGGER.debug(calendar, date, summary, details, length, event, from_time)
    event = service.events().insert(calendarId=calendar, body=event).execute()
    LOGGER.debug(event.items())
    print(
        f'Created event "{summary}" ({f"{duration}h" if duration else "full day"}) on calendar {event["organizer"]["displayName"]}'
    )
    event_data = {
        "id": event["id"],
        "next_slot": end.strftime("%H:%M") if haveLength else from_time,
        "link": event["htmlLink"],
    }
    return event_data


def execute(config_dir):
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    get_credentials(config_dir)

    service = build("calendar", "v3", credentials=creds)

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
    print("Getting the upcoming 10 events")
    events_result = (
        service.events()
        .list(
            calendarId="c_bu7esjsc8qt8vc6gtjruuq94js@group.calendar.google.com",
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    if not events:
        print("No upcoming events found.")
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        print(start, event["summary"])
