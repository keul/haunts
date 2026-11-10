"""Tests for `--execute read` services selection."""

import unittest
from datetime import time, timedelta
from unittest import mock

from haunts import download, spreadsheet


def config(**options):
    def fake_get(name, default=None):
        return options.get(name, default)

    return fake_get


class TestGetReadServices(unittest.TestCase):
    def services(self, skip=(), **options):
        options.setdefault("USER_EMAIL", "me@bopen.eu")
        fake = config(**options)
        with mock.patch("haunts.download.get", fake), mock.patch("haunts.proton.get", fake):
            return download.get_read_services(skip=skip)

    def test_default_with_proton(self):
        self.assertEqual(self.services(PROTON_CLI="proton"), ["google", "proton"])

    def test_default_without_proton(self):
        self.assertEqual(self.services(), ["google"])

    def test_proton_only(self):
        self.assertEqual(
            self.services(READ_FROM_SERVICES="proton", PROTON_CLI="proton"), ["proton"]
        )

    def test_google_only(self):
        self.assertEqual(
            self.services(READ_FROM_SERVICES="google", PROTON_CLI="proton"), ["google"]
        )

    def test_spaces_and_case(self):
        self.assertEqual(
            self.services(READ_FROM_SERVICES=" Proton , GOOGLE ", PROTON_CLI="proton"),
            ["google", "proton"],
        )

    def test_explicit_proton_without_cli(self):
        with self.assertRaisesRegex(download.ConfigurationError, "PROTON_CLI"):
            self.services(READ_FROM_SERVICES="google,proton")

    def test_unknown_service(self):
        with self.assertRaisesRegex(download.ConfigurationError, "outlook"):
            self.services(READ_FROM_SERVICES="google,outlook")

    def test_skip(self):
        self.assertEqual(self.services(skip=["proton"], PROTON_CLI="proton"), ["google"])
        self.assertEqual(self.services(skip=["google"], PROTON_CLI="proton"), ["proton"])

    def test_skip_explicit_proton_without_cli(self):
        self.assertEqual(
            self.services(skip=["proton"], READ_FROM_SERVICES="google,proton"), ["google"]
        )

    def test_proton_without_email(self):
        with self.assertRaisesRegex(download.ConfigurationError, "PROTON_EMAIL"):
            self.services(PROTON_CLI="proton", USER_EMAIL="")

    def test_proton_email_only(self):
        self.assertEqual(
            self.services(
                READ_FROM_SERVICES="proton",
                PROTON_CLI="proton",
                USER_EMAIL="",
                PROTON_EMAIL="me@pm.me",
            ),
            ["proton"],
        )

    def test_skip_everything(self):
        with self.assertRaisesRegex(download.ConfigurationError, "No calendar service"):
            self.services(skip=["google", "proton"], PROTON_CLI="proton")


class TestFilterMyEvents(unittest.TestCase):
    def test_answers(self):
        def event(id, status):
            return {
                "id": id,
                "creator": {"email": "other@bopen.eu"},
                "attendees": [{"email": "me@bopen.eu", "responseStatus": status}],
            }

        events = [
            event("accepted", "accepted"),
            event("tentative", "tentative"),
            event("needsAction", "needsAction"),
            event("declined", "declined"),
            {"id": "mine", "creator": {"email": "me@bopen.eu"}},
            {"id": "not invited", "creator": {"email": "other@bopen.eu"}},
        ]
        with mock.patch("haunts.download.get", config(USER_EMAIL="me@bopen.eu")):
            self.assertEqual(
                [e["id"] for e in download.filter_my_events(events)],
                ["accepted", "tentative", "needsAction", "mine"],
            )


class TestDescribeTiming(unittest.TestCase):
    def test_timed(self):
        event = {"start": {"dateTime": "2026-11-10T10:30:00+01:00"}}
        for minutes, expected in (
            (60, "at 10:30:00 (lasts 1 hour)"),
            (90, "at 10:30:00 (lasts 1.5 hours)"),
            (120, "at 10:30:00 (lasts 2 hours)"),
            (20, "at 10:30:00 (lasts 0.33 hours)"),
        ):
            with self.subTest(minutes=minutes):
                self.assertEqual(
                    download.describe_timing(event, time(10, 30), timedelta(minutes=minutes)),
                    expected,
                )

    def test_full_day(self):
        event = {"start": {"date": "2026-11-10"}}
        self.assertEqual(download.describe_timing(event, time(0, 0), timedelta(days=1)), "full day")
        self.assertEqual(
            download.describe_timing(event, time(0, 0), timedelta(days=3)),
            "full day (3 days)",
        )


class TestGetCalendarsById(unittest.TestCase):
    def test_ids_and_read_from(self):
        sheet = mock.MagicMock()
        sheet.values().get().execute.return_value = {
            "values": [
                ["team@group", "Team"],
                ["accounting@group", "Customer meetings", "team@group"],
                ["accounting@group", "Customer meetings alias"],
                ["other@group", "Other", ""],
                ["proton@group", "Proton project", "proton:cal1"],
                ["incomplete"],
            ]
        }
        with mock.patch("haunts.spreadsheet.get", config(CONTROLLER_SHEET_DOCUMENT_ID="x")):
            self.assertEqual(
                spreadsheet.get_calendars_by_id(sheet),
                {
                    "team@group": "Customer meetings",
                    "accounting@group": "Customer meetings",
                    "other@group": "Other",
                    "proton@group": "Proton project",
                    "proton:cal1": "Proton project",
                },
            )


if __name__ == "__main__":
    unittest.main()
