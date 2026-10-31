"""Tests for `--execute read` services selection."""

import unittest
from unittest import mock

from haunts import download


def config(**options):
    def fake_get(name, default=None):
        return options.get(name, default)

    return fake_get


class TestGetReadServices(unittest.TestCase):
    def services(self, skip=(), **options):
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

    def test_skip_everything(self):
        with self.assertRaisesRegex(download.ConfigurationError, "No calendar service"):
            self.services(skip=["google", "proton"], PROTON_CLI="proton")


if __name__ == "__main__":
    unittest.main()
