#!/usr/bin/env python3

import json
import multiprocessing
import stat
import sys
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "scripts")
)

from thermal_guardian_latch import EmergencyLatch


def create_in_child(path):
    EmergencyLatch(path).create(
        "GPU junction",
        101.0,
        100.0,
        "EMERGENCY",
        "Child process emergency",
    )


class EmergencyLatchTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.path = (
            Path(self.temp.name)
            / "emergency-latch.json"
        )

        self.latch = EmergencyLatch(self.path)

    def trigger(self):
        return self.latch.create(
            "GPU junction",
            101.0,
            100.0,
            "EMERGENCY",
            "Thermal threshold reached",
        )

    def test_initial_state_clear(self):
        self.assertEqual(
            self.latch.status()["state"],
            "CLEAR",
        )
        self.assertFalse(
            self.latch.blocks_computation()
        )

    def test_emergency_blocks_computation(self):
        result = self.trigger()

        self.assertEqual(result["state"], "LATCHED")
        self.assertTrue(
            self.latch.blocks_computation()
        )

    def test_record_contents(self):
        record = self.trigger()["record"]

        self.assertEqual(record["sensor"], "GPU junction")
        self.assertEqual(record["temperature"], 101.0)
        self.assertEqual(record["threshold"], 100.0)
        self.assertEqual(record["level"], "EMERGENCY")
        self.assertTrue(record["event_id"])
        self.assertTrue(record["timestamp"])

    def test_persistence_across_instances(self):
        first = self.trigger()

        recovered = EmergencyLatch(self.path).status()

        self.assertEqual(first, recovered)

    def test_persistence_across_processes(self):
        process = multiprocessing.Process(
            target=create_in_child,
            args=(self.path,),
        )

        process.start()
        process.join(timeout=5)

        if process.is_alive():
            process.kill()
            process.join()
            self.fail("Child process timed out")

        self.assertEqual(process.exitcode, 0)
        self.assertTrue(
            self.latch.blocks_computation()
        )

    def test_original_emergency_preserved(self):
        original = self.trigger()

        subsequent = self.latch.create(
            "CPU package",
            102.0,
            100.0,
            "CRITICAL",
            "Later escalation",
        )

        self.assertEqual(original, subsequent)

    def test_corrupt_record_blocks_computation(self):
        self.path.write_text("{broken json")

        self.assertEqual(
            self.latch.status()["state"],
            "FAULT",
        )

        self.assertTrue(
            self.latch.blocks_computation()
        )

    def test_empty_record_blocks_computation(self):
        self.path.write_text("")

        self.assertTrue(
            self.latch.blocks_computation()
        )

    def test_incomplete_record_blocks_computation(self):
        self.path.write_text(
            json.dumps({"version": 1})
        )

        self.assertEqual(
            self.latch.status()["state"],
            "FAULT",
        )

    def test_corrupt_record_not_overwritten(self):
        self.path.write_text("corrupt emergency")

        self.trigger()

        self.assertEqual(
            self.path.read_text(),
            "corrupt emergency",
        )

    def test_missing_directory_blocks_computation(self):
        latch = EmergencyLatch(
            self.path.parent / "missing" / self.path.name
        )

        self.assertTrue(latch.blocks_computation())

    def test_permission_error_blocks_computation(self):
        self.trigger()

        with patch.object(
            Path,
            "open",
            side_effect=PermissionError("Denied"),
        ):
            self.assertTrue(
                self.latch.blocks_computation()
            )

    def test_broken_symlink_blocks_computation(self):
        self.path.symlink_to(
            self.path.parent / "missing-file"
        )

        self.assertTrue(
            self.latch.blocks_computation()
        )

    def test_record_permissions(self):
        self.trigger()

        permissions = stat.S_IMODE(
            self.path.stat().st_mode
        )

        self.assertEqual(permissions, 0o600)

    def test_invalid_emergency_rejected(self):
        with self.assertRaises(ValueError):
            self.latch.create(
                "GPU junction",
                80,
                100,
                "NORMAL",
                "Invalid event",
            )

        self.assertFalse(
            self.latch.blocks_computation()
        )

    def test_nonfinite_temperature_rejected(self):
        with self.assertRaises(ValueError):
            self.latch.create(
                "GPU junction",
                float("nan"),
                100,
                "EMERGENCY",
                "Invalid reading",
            )

    def test_critical_event_latched(self):
        result = self.latch.create(
            "CPU package",
            102,
            100,
            "CRITICAL",
            "Absolute critical temperature",
        )

        self.assertEqual(
            result["record"]["level"],
            "CRITICAL",
        )

    def test_temporary_file_cleanup(self):
        self.trigger()

        self.assertEqual(
            list(self.path.parent.iterdir()),
            [self.path],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
