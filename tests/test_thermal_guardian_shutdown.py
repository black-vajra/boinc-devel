"""Shutdown backend tests using harmless commands."""

import sys
import time
import unittest

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "scripts"),
)

from thermal_guardian_shutdown import ShutdownBackend


TRUE = ("/usr/bin/true",)
FALSE = ("/usr/bin/false",)
MISSING = ("/nonexistent/thermal-guardian-command",)
SLEEP = ("/usr/bin/sleep", "10")


class ShutdownBackendTests(unittest.TestCase):

    def test_default_is_harmless(self):
        result = ShutdownBackend().execute()

        self.assertTrue(result.accepted)
        self.assertEqual(len(result.attempts), 1)

    def test_primary_success(self):
        result = ShutdownBackend(
            primary=TRUE,
            fallback=FALSE,
        ).execute()

        self.assertTrue(result.accepted)
        self.assertEqual(len(result.attempts), 1)
        self.assertEqual(
            result.attempts[0].status, "ACCEPTED"
        )

    def test_primary_failure(self):
        result = ShutdownBackend(
            primary=FALSE,
            fallback=TRUE,
        ).execute()

        self.assertTrue(result.accepted)
        self.assertEqual(len(result.attempts), 2)
        self.assertEqual(
            result.attempts[0].status, "FAILED"
        )
        self.assertEqual(
            result.attempts[1].status, "ACCEPTED"
        )

    def test_primary_missing(self):
        result = ShutdownBackend(
            primary=MISSING,
            fallback=TRUE,
        ).execute()

        self.assertTrue(result.accepted)
        self.assertEqual(
            result.attempts[0].status, "ERROR"
        )

    def test_primary_timeout(self):
        started = time.monotonic()

        result = ShutdownBackend(
            primary=SLEEP,
            fallback=TRUE,
            primary_timeout=0.2,
        ).execute()

        self.assertTrue(result.accepted)
        self.assertEqual(
            result.attempts[0].status, "TIMEOUT"
        )
        self.assertLess(
            time.monotonic() - started, 1.5
        )

    def test_both_commands_fail(self):
        result = ShutdownBackend(
            primary=FALSE,
            fallback=FALSE,
        ).execute()

        self.assertFalse(result.accepted)
        self.assertEqual(len(result.attempts), 2)

    def test_fallback_missing(self):
        result = ShutdownBackend(
            primary=FALSE,
            fallback=MISSING,
        ).execute()

        self.assertFalse(result.accepted)
        self.assertEqual(
            result.attempts[1].status, "ERROR"
        )

    def test_fallback_timeout(self):
        result = ShutdownBackend(
            primary=FALSE,
            fallback=SLEEP,
            fallback_timeout=0.2,
        ).execute()

        self.assertFalse(result.accepted)
        self.assertEqual(
            result.attempts[1].status, "TIMEOUT"
        )

    def test_both_commands_timeout(self):
        started = time.monotonic()

        result = ShutdownBackend(
            primary=SLEEP,
            fallback=SLEEP,
            primary_timeout=0.2,
            fallback_timeout=0.2,
        ).execute()

        self.assertFalse(result.accepted)
        self.assertEqual(
            [a.status for a in result.attempts],
            ["TIMEOUT", "TIMEOUT"],
        )
        self.assertLess(
            time.monotonic() - started, 1.5
        )

    def test_invalid_timeout(self):
        for value in (0, -1, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ShutdownBackend(primary_timeout=value)

    def test_empty_command(self):
        with self.assertRaises(ValueError):
            ShutdownBackend(primary=())

    def test_callback_interface(self):
        backend = ShutdownBackend()
        result = backend(None)

        self.assertTrue(result.accepted)


if __name__ == "__main__":
    unittest.main()
