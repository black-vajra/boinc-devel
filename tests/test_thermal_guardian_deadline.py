"""Persistent emergency deadline regression tests."""

import stat
import sys
import tempfile
import time
import unittest

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "scripts"),
)

from thermal_guardian_deadline import DeadlineRecord


class DeadlineTests(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)

        self.path = Path(directory.name) / "deadline.json"
        self.store = DeadlineRecord(self.path)
        self.initial = time.monotonic() + 7
        self.record = self.store.register(self.initial)
        self.event = self.record["event_id"]

    def test_registration(self):
        self.assertEqual(
            self.record["deadline"], self.initial
        )
        self.assertEqual(
            stat.S_IMODE(self.path.stat().st_mode), 0o600
        )

    def test_recreation(self):
        self.assertEqual(
            DeadlineRecord(self.path).load(), self.record
        )

    def test_existing_emergency_preserved(self):
        with self.assertRaises(FileExistsError):
            self.store.register(time.monotonic() + 7)

        self.assertEqual(self.store.load(), self.record)

    def test_override(self):
        updated = self.store.override(
            self.event, time.monotonic() + 30
        )

        self.assertEqual(
            updated["initial_deadline"], self.initial
        )
        self.assertTrue(updated["override_used"])
        self.assertEqual(updated["state"], "OVERRIDE")
        self.assertFalse(self.store.due())

    def test_override_cannot_renew(self):
        self.store.override(
            self.event, time.monotonic() + 30
        )

        with self.assertRaises(RuntimeError):
            self.store.override(
                self.event, time.monotonic() + 30
            )

    def test_shutdown_irreversible(self):
        self.store.request_shutdown(self.event)

        self.assertTrue(self.store.due())

        with self.assertRaises(RuntimeError):
            self.store.override(
                self.event, time.monotonic() + 30
            )

    def test_shutdown_idempotent(self):
        result = self.store.request_shutdown(self.event)

        self.assertEqual(
            self.store.request_shutdown(self.event), result
        )

    def test_shutdown_survives_recreation(self):
        result = self.store.request_shutdown(self.event)
        recovered = DeadlineRecord(self.path)

        self.assertTrue(recovered.due())
        self.assertEqual(recovered.load(), result)

    def test_previous_boot_rejected(self):
        self.store.boot_id = "different-boot"

        with self.assertRaises(RuntimeError):
            self.store.load()

    def test_expired_countdown(self):
        path = self.path.parent / "expired.json"
        store = DeadlineRecord(path)
        record = store.register(time.monotonic() - 1)

        self.assertTrue(store.due())

        with self.assertRaises(RuntimeError):
            store.override(
                record["event_id"],
                time.monotonic() + 30,
            )


if __name__ == "__main__":
    unittest.main()
