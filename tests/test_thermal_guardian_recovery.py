"""Persistent recovery interlock tests."""

import os
import stat
import sys
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "scripts"),
)

from thermal_guardian_recovery import RecoveryState


class RecoveryTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.path = Path(self.temp.name) / "state.json"
        self.state = RecoveryState(self.path)

    def authorize(self):
        return self.state.authorize_recovery(
            "Administrator inspection completed"
        )

    def arm(self):
        self.authorize()
        return self.state.arm()

    def test_uninitialized(self):
        self.assertEqual(
            self.state.status(), "UNINITIALIZED"
        )
        self.assertFalse(
            self.state.permits_new_session()
        )

    def test_authorized_recovery(self):
        self.assertEqual(self.authorize(), "CLEAN")
        self.assertTrue(
            self.state.permits_new_session()
        )

    def test_arm(self):
        self.assertEqual(self.arm(), "ARMED")
        self.assertFalse(
            self.state.permits_new_session()
        )

    def test_arm_without_authorization(self):
        with self.assertRaises(RuntimeError):
            self.state.arm()

    def test_interrupted_session(self):
        self.arm()

        restarted = RecoveryState(self.path)

        self.assertEqual(restarted.status(), "ARMED")
        self.assertFalse(
            restarted.permits_new_session()
        )

        with self.assertRaises(RuntimeError):
            restarted.arm()

    def test_emergency(self):
        self.arm()

        self.state.emergency("Synthetic thermal emergency")

        self.assertEqual(
            self.state.status(), "EMERGENCY"
        )

        self.assertFalse(
            self.state.permits_new_session()
        )

    def test_emergency_blocks_rearm(self):
        self.arm()
        self.state.emergency("Synthetic emergency")

        with self.assertRaises(RuntimeError):
            self.state.arm()

    def test_orderly_shutdown(self):
        self.arm()

        result = self.state.clean_shutdown(
            computation_stopped=True,
            emergency_clear=True,
        )

        self.assertEqual(result, "CLEAN")
        self.assertTrue(
            self.state.permits_new_session()
        )

    def test_computation_still_running(self):
        self.arm()

        with self.assertRaises(RuntimeError):
            self.state.clean_shutdown(
                computation_stopped=False,
                emergency_clear=True,
            )

        self.assertEqual(
            self.state.status(), "ARMED"
        )

    def test_unresolved_emergency(self):
        self.arm()

        with self.assertRaises(RuntimeError):
            self.state.clean_shutdown(
                computation_stopped=True,
                emergency_clear=False,
            )

        self.assertEqual(
            self.state.status(), "ARMED"
        )

    def test_emergency_cannot_be_clean_shutdown(self):
        self.arm()
        self.state.emergency("Synthetic emergency")

        with self.assertRaises(RuntimeError):
            self.state.clean_shutdown(
                computation_stopped=True,
                emergency_clear=True,
            )

    def test_corrupt_record(self):
        self.path.write_text("not-json")

        self.assertEqual(
            self.state.status(), "FAULT"
        )
        self.assertFalse(
            self.state.permits_new_session()
        )

    def test_invalid_state(self):
        self.path.write_text(
            '{"version":1,"state":"UNKNOWN"}'
        )

        self.assertEqual(
            self.state.status(), "FAULT"
        )

    def test_missing_directory(self):
        missing = RecoveryState(
            self.path.parent / "missing/state.json"
        )

        self.assertEqual(missing.status(), "FAULT")

    def test_symlink_rejected(self):
        target = self.path.parent / "target.json"

        target.write_text(
            '{"version":1,"state":"CLEAN"}'
        )

        self.path.symlink_to(target)

        self.assertEqual(
            self.state.status(), "FAULT"
        )

    def test_fifo_rejected(self):
        os.mkfifo(self.path)

        self.assertEqual(
            self.state.status(), "FAULT"
        )

    def test_private_permissions(self):
        self.arm()

        mode = stat.S_IMODE(self.path.stat().st_mode)

        self.assertEqual(mode, 0o600)

    def test_recovery_reason_required(self):
        with self.assertRaises(ValueError):
            self.state.authorize_recovery("")

    def test_failed_arm_persistence(self):
        self.authorize()

        with patch(
            "thermal_guardian_recovery.os.fsync",
            side_effect=OSError("Synthetic disk failure"),
        ):
            with self.assertRaises(OSError):
                self.state.arm()

        self.assertEqual(self.state.status(), "CLEAN")


if __name__ == "__main__":
    unittest.main()
