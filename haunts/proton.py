"""Read events from Proton Calendar.

Proton does not provide a public API: calendar data is end-to-end encrypted and can only be
decrypted client side. haunts relies on proton-cli (https://proton-cli.lerchster.dev/), a
command line client that handles login and decryption, and parses its JSON output.
"""

import json
import os
import shutil
import subprocess

from dateutil import parser as date_parser

from . import LOGGER
from .ini import get

# Prefix used in the "read_from" column of the config sheet to reference a Proton calendar
PROTON_PREFIX = "proton:"
# Key used for Proton events not found in any calendar configured in the config sheet
PROTON_CATCH_ALL = f"{PROTON_PREFIX}*"

# Kinds of calendars not read by the catch-all, unless explicitly configured in the config sheet
IGNORED_CALENDAR_KINDS = {"holidays"}

# proton-cli exit codes, see https://proton-cli.lerchster.dev/using/output/
EXIT_CODES = {
    1: "invalid input",
    2: "authentication failed: run `proton account login` and try again",
    3: "not found",
    4: "ambiguous input or conflict",
    5: "network or server problem (rate limiting included): retry later",
    6: "refused by your proton-cli confirmation policy",
    7: "internal proton-cli error",
    8: "not supported by your proton-cli version",
}


class ProtonError(Exception):
    """Raised when Proton Calendar events cannot be read."""


def is_enabled():
    """Proton support is enabled when PROTON_CLI is set in the configuration."""
    return bool(get("PROTON_CLI", "").strip())


def is_proton_calendar(calendar_id):
    return bool(calendar_id) and calendar_id.startswith(PROTON_PREFIX)


def proton_calendar_key(calendar_id):
    """From a Proton calendar id to the value used in the config sheet."""
    return f"{PROTON_PREFIX}{calendar_id}"


def event_marker(event):
    """Unique reference to a Proton event (occurrence), stored in the "Link" column.

    Occurrences of a recurring event share the same id, so the occurrence is added.
    """
    marker = f"{PROTON_PREFIX}{event['calendar_id']}/{event['id']}"
    if event.get("occurrence"):
        marker += f"@{event['occurrence']}"
    return marker


def _cli_path():
    cli = get("PROTON_CLI", "").strip()
    path = shutil.which(cli)
    if not path:
        raise ProtonError(
            f'proton-cli executable "{cli}" not found. '
            "Install it (https://proton-cli.lerchster.dev/install/) "
            "or fix PROTON_CLI in haunts.ini."
        )
    return path


def _run(args):
    env = {
        **os.environ,
        # Get event times in the configured timezone
        "TZ": get("TIMEZONE", "Etc/GMT"),
        # Never wait for user input
        "PROTON_NO_INPUT": "1",
        "PROTON_NO_UPDATE_CHECK": "1",
        "NO_COLOR": "1",
    }
    profile = get("PROTON_PROFILE", "").strip()
    if profile:
        env["PROTON_PROFILE"] = profile
    command = [_cli_path(), *args, "--output", "json"]
    LOGGER.debug(f"Running {' '.join(command)}")
    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    except OSError as err:
        raise ProtonError(f"Cannot run proton-cli: {err}") from err
    if result.returncode != 0:
        reason = EXIT_CODES.get(result.returncode, f"exit code {result.returncode}")
        stderr = result.stderr.strip()
        raise ProtonError(f"proton-cli failed ({reason})" + (f": {stderr}" if stderr else ""))
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as err:
        raise ProtonError(f"Cannot parse proton-cli output: {err}") from err


def normalize_event(event):
    """Convert a proton-cli event to the same structure of a Google Calendar event.

    Only keys used by haunts are provided. As Proton events have no web link,
    a marker that identifies the event is used instead.
    """
    if event.get("all_day"):
        # All-day events start at midnight of their first day,
        # and end at the midnight after their last day
        start = {"date": event["start"][:10]}
        end = {"date": event["end"][:10]}
    else:
        start = {"dateTime": date_parser.isoparse(event["start"]).isoformat()}
        end = {"dateTime": date_parser.isoparse(event["end"]).isoformat()}
    return {
        "id": event["id"],
        "summary": event.get("title") or "No summary",
        "description": event.get("description", ""),
        "start": start,
        "end": end,
        "htmlLink": event_marker(event),
        "calendar_id": proton_calendar_key(event["calendar_id"]),
        "proton_calendar_id": event["calendar_id"],
        "uid": event.get("uid", ""),
        "organizer": event.get("organizer", ""),
        "source": "Proton",
    }


def get_events_at(date):
    """Get events from all Proton calendars in a specific date.

    Cancelled events are ignored.
    """
    day = date.strftime("%Y-%m-%d")
    data = _run(["calendar", "events", "list", "--after", day, "--before", day, "--limit", "0"])
    events = data.get("events", [])
    return [normalize_event(e) for e in events if e.get("status") != "cancelled"]


def get_calendar_ids(kinds):
    """Get ids of Proton calendars of the given kinds (personal, shared, subscribed, holidays)."""
    data = _run(["calendar", "settings", "calendars", "list", "--limit", "0"])
    return {c["id"] for c in data.get("calendars", []) if c.get("kind") in kinds}
