"""Tests for Proton Calendar support."""

import json
import subprocess
import unittest
from datetime import date
from unittest import mock

from haunts import download, proton

CONFIG = {
    "PROTON_CLI": "proton",
    "USER_EMAIL": "me@bopen.eu",
    "TIMEZONE": "Europe/Rome",
}


def fake_get(name, default=None):
    return CONFIG.get(name, default)


def proton_event(**kwargs):
    event = {
        "id": "ev1",
        "calendar_id": "cal1",
        "title": "Standup",
        "description": "Daily meeting",
        "start": "2026-10-31T09:00:00+01:00",
        "end": "2026-10-31T09:30:00+01:00",
        "all_day": False,
        "zone": "Europe/Rome",
        "reminders": [],
        "attendees": [],
        "status": "confirmed",
    }
    event.update(kwargs)
    return event


def completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


@mock.patch("haunts.proton.get", fake_get)
@mock.patch("haunts.proton.shutil.which", lambda cli: f"/usr/local/bin/{cli}")
class TestProton(unittest.TestCase):
    def test_is_enabled(self):
        self.assertTrue(proton.is_enabled())
        with mock.patch("haunts.proton.get", lambda name, default=None: default):
            self.assertFalse(proton.is_enabled())

    def test_is_proton_calendar(self):
        self.assertTrue(proton.is_proton_calendar("proton:cal1"))
        self.assertFalse(proton.is_proton_calendar("foo@group.calendar.google.com"))
        self.assertFalse(proton.is_proton_calendar(None))

    def test_normalize_timed_event(self):
        event = proton.normalize_event(proton_event())
        self.assertEqual(event["id"], "ev1")
        self.assertEqual(event["summary"], "Standup")
        self.assertEqual(event["description"], "Daily meeting")
        self.assertEqual(event["start"], {"dateTime": "2026-10-31T09:00:00+01:00"})
        self.assertEqual(event["end"], {"dateTime": "2026-10-31T09:30:00+01:00"})
        self.assertEqual(event["calendar_id"], "proton:cal1")
        self.assertEqual(event["htmlLink"], "proton:cal1/ev1")
        self.assertEqual(event["source"], "Proton")
        self.assertEqual(event["uid"], "")
        self.assertEqual(event["organizer"], "")

    def test_normalize_utc_event(self):
        event = proton.normalize_event(
            proton_event(start="2026-10-31T08:00:00Z", end="2026-10-31T08:30:00.5Z")
        )
        self.assertEqual(event["start"], {"dateTime": "2026-10-31T08:00:00+00:00"})
        self.assertEqual(event["end"], {"dateTime": "2026-10-31T08:30:00.500000+00:00"})

    def test_normalize_all_day_event(self):
        event = proton.normalize_event(
            proton_event(
                all_day=True, start="2026-10-31T00:00:00+01:00", end="2026-11-01T00:00:00+01:00"
            )
        )
        self.assertEqual(event["start"], {"date": "2026-10-31"})
        self.assertEqual(event["end"], {"date": "2026-11-01"})

    def test_normalize_recurring_event(self):
        event = proton.normalize_event(
            proton_event(rrule="FREQ=DAILY", occurrence="2026-10-31T09:00")
        )
        self.assertEqual(event["htmlLink"], "proton:cal1/ev1@2026-10-31T09:00")

    def test_normalize_missing_title(self):
        event = proton.normalize_event(proton_event(title=""))
        self.assertEqual(event["summary"], "No summary")

    @mock.patch("haunts.proton.subprocess.run")
    def test_get_events_at(self, run):
        run.return_value = completed(
            json.dumps(
                {
                    "events": [
                        proton_event(),
                        proton_event(id="ev2", status="cancelled"),
                        proton_event(id="ev3", attendees=[attendee("me@bopen.eu", "accepted")]),
                        proton_event(id="ev4", attendees=[attendee("me@bopen.eu", "declined")]),
                    ],
                    "count": 2,
                }
            )
        )
        events = proton.get_events_at(date(2026, 10, 31))
        self.assertEqual([e["id"] for e in events], ["ev1", "ev3"])
        args, kwargs = run.call_args
        self.assertEqual(
            args[0],
            [
                "/usr/local/bin/proton",
                "calendar",
                "events",
                "list",
                "--after",
                "2026-10-31",
                "--before",
                "2026-10-31",
                "--limit",
                "0",
                "--output",
                "json",
            ],
        )
        self.assertEqual(kwargs["env"]["TZ"], "Europe/Rome")
        self.assertEqual(kwargs["env"]["PROTON_NO_INPUT"], "1")
        self.assertNotIn("PROTON_PROFILE", kwargs["env"])

    @mock.patch("haunts.proton.subprocess.run")
    def test_profile(self, run):
        run.return_value = completed(json.dumps({"events": [], "count": 0}))
        with mock.patch.dict(CONFIG, {"PROTON_PROFILE": "work"}):
            proton.get_events_at(date(2026, 10, 31))
        self.assertEqual(run.call_args.kwargs["env"]["PROTON_PROFILE"], "work")

    @mock.patch("haunts.proton.subprocess.run")
    def test_auth_failure(self, run):
        run.return_value = completed(returncode=2, stderr="Error: not signed in")
        with self.assertRaisesRegex(proton.ProtonError, "proton account login"):
            proton.get_events_at(date(2026, 10, 31))

    @mock.patch("haunts.proton.subprocess.run")
    def test_invalid_output(self, run):
        run.return_value = completed("not json")
        with self.assertRaises(proton.ProtonError):
            proton.get_events_at(date(2026, 10, 31))

    def test_parse_version(self):
        self.assertEqual(proton.parse_version("proton version 5.4.0"), (5, 4, 0))
        self.assertEqual(proton.parse_version("proton version v12.0.3-dev"), (12, 0, 3))
        self.assertIsNone(proton.parse_version("proton version dev"))

    @mock.patch("haunts.proton.subprocess.run")
    def test_check_version(self, run):
        for output, warning in (
            ("proton version 5.4.0\n", None),
            ("proton version 6.0.1\n", None),
            ("proton version 5.3.9\n", "5.3.9 found"),
            ("proton version dev\n", "Cannot detect"),
        ):
            with self.subTest(output=output):
                run.return_value = completed(output)
                result = proton.check_version()
                if warning:
                    self.assertIn(warning, result)
                else:
                    self.assertIsNone(result)
        self.assertEqual(run.call_args.args[0], ["/usr/local/bin/proton", "-v"])

    @mock.patch("haunts.proton.subprocess.run")
    def test_check_version_failure(self, run):
        run.return_value = completed(returncode=7, stderr="boom")
        with self.assertRaises(proton.ProtonError):
            proton.check_version()

    def test_missing_cli(self):
        with mock.patch("haunts.proton.shutil.which", lambda cli: None):
            with self.assertRaisesRegex(proton.ProtonError, "not found"):
                proton.get_events_at(date(2026, 10, 31))

    @mock.patch("haunts.proton.subprocess.run")
    def test_get_calendar_ids(self, run):
        run.return_value = completed(
            json.dumps(
                {
                    "calendars": [
                        {"id": "h1", "name": "Giorni festivi in Italia", "kind": "holidays"},
                        {"id": "c1", "name": "My calendar", "kind": "personal"},
                    ],
                    "count": 2,
                }
            )
        )
        self.assertEqual(proton.get_calendar_ids({"holidays"}), {"h1"})
        self.assertEqual(
            run.call_args.args[0][1:],
            ["calendar", "settings", "calendars", "list", "--limit", "0", "--output", "json"],
        )


def attendee(email, answer="pending", role="required"):
    return {"answer": answer, "email": email, "role": role}


class TestMyEvents(unittest.TestCase):
    ME = {"l.fabbri@bopen.eu"}

    def is_mine(self, **kwargs):
        return proton.is_my_event(proton_event(**kwargs), self.ME)

    def test_no_attendees(self):
        self.assertTrue(self.is_mine(attendees=[]))

    def test_answers(self):
        for answer, expected in (
            ("accepted", True),
            ("pending", True),
            ("tentative", True),
            ("declined", False),
        ):
            with self.subTest(answer=answer):
                self.assertEqual(
                    self.is_mine(
                        attendees=[
                            attendee("other@bopen.eu", "accepted"),
                            attendee("L.Fabbri@bopen.eu", answer),
                        ]
                    ),
                    expected,
                )

    def test_not_invited(self):
        self.assertFalse(self.is_mine(attendees=[attendee("other@bopen.eu", "accepted")]))

    def test_organizer(self):
        self.assertTrue(
            self.is_mine(
                organizer="l.fabbri@bopen.eu", attendees=[attendee("other@bopen.eu", "declined")]
            )
        )

    def test_old_proton_cli(self):
        # Answers are not available: keep the event
        self.assertTrue(self.is_mine(attendees=["other@bopen.eu"]))


class TestMyEmails(unittest.TestCase):
    def emails(self, **options):
        with mock.patch("haunts.proton.get", lambda name, default=None: options.get(name, default)):
            return proton.get_my_emails()

    def test_user_email(self):
        self.assertEqual(self.emails(USER_EMAIL="l.fabbri@bopen.eu"), {"l.fabbri@bopen.eu"})

    def test_proton_email(self):
        self.assertEqual(
            self.emails(USER_EMAIL="l.fabbri@bopen.eu", PROTON_EMAIL=" Luca@Proton.me, l@pm.me "),
            {"luca@proton.me", "l@pm.me"},
        )

    def test_none(self):
        self.assertEqual(self.emails(), set())


@mock.patch("haunts.proton.get_calendar_ids", lambda kinds: {"holidays_cal"})
class TestGetProtonEvents(unittest.TestCase):
    @mock.patch("haunts.proton.get_events_at")
    def test_holidays_ignored(self, get_events_at):
        get_events_at.return_value = [
            proton.normalize_event(proton_event(id="h1", calendar_id="holidays_cal")),
            proton.normalize_event(proton_event(id="ev1", calendar_id="cal1")),
        ]
        events = download.get_proton_events(set(), date(2026, 10, 31), set())
        self.assertEqual([e["id"] for e in events], ["ev1"])

    @mock.patch("haunts.proton.get_events_at")
    def test_holidays_explicitly_configured(self, get_events_at):
        get_events_at.return_value = [
            proton.normalize_event(proton_event(id="h1", calendar_id="holidays_cal")),
        ]
        events = download.get_proton_events({"proton:holidays_cal"}, date(2026, 10, 31), set())
        self.assertEqual([e["calendar_id"] for e in events], ["proton:holidays_cal"])

    @mock.patch("haunts.proton.get_events_at")
    def test_project_from_organizer(self, get_events_at):
        get_events_at.return_value = [
            proton.normalize_event(
                proton_event(id="ev1", organizer="c_123@group.calendar.google.com")
            ),
            proton.normalize_event(proton_event(id="ev2", organizer="customer@example.com")),
            # Mapped calendars win over organizer
            proton.normalize_event(
                proton_event(
                    id="ev3", calendar_id="mapped", organizer="c_123@group.calendar.google.com"
                )
            ),
        ]
        events = download.get_proton_events(
            {"proton:mapped"},
            date(2026, 10, 31),
            set(),
            organizer_projects={"c_123@group.calendar.google.com": "ESA"},
        )
        self.assertEqual(
            [(e["id"], e["calendar_id"], e.get("project")) for e in events],
            [
                ("ev1", proton.PROTON_CATCH_ALL, "ESA"),
                ("ev2", proton.PROTON_CATCH_ALL, None),
                ("ev3", "proton:mapped", None),
            ],
        )
        self.assertEqual(events[0]["source"], "Proton, by organizer")

    @mock.patch("haunts.proton.get_events_at")
    def test_google_duplicates(self, get_events_at):
        get_events_at.return_value = [
            proton.normalize_event(proton_event(id="ev1", uid="abc@google.com")),
            proton.normalize_event(proton_event(id="ev2", uid="def@proton.me")),
            proton.normalize_event(proton_event(id="ev3")),
        ]
        events = download.get_proton_events(
            set(), date(2026, 10, 31), set(), google_uids={"abc@google.com"}
        )
        self.assertEqual([e["id"] for e in events], ["ev2", "ev3"])

    @mock.patch("haunts.proton.get_events_at")
    def test_catch_all_and_duplicates(self, get_events_at):
        get_events_at.return_value = [
            proton.normalize_event(proton_event()),
            proton.normalize_event(proton_event(id="ev2", calendar_id="other")),
            # same event returned twice
            proton.normalize_event(proton_event()),
        ]
        events = download.get_proton_events({"proton:cal1"}, date(2026, 10, 31), set())
        self.assertEqual(
            [(e["id"], e["calendar_id"]) for e in events],
            [("ev1", "proton:cal1"), ("ev2", proton.PROTON_CATCH_ALL)],
        )


if __name__ == "__main__":
    unittest.main()
