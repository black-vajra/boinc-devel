#!/usr/bin/env python3

import sys
import unittest

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "scripts")
)

from thermal_guardian_controller import (
    EmergencyController,
    State,
)


class EmergencyControllerTests(unittest.TestCase):

    def setUp(self):
        self.controller = EmergencyController(7, 30)

    def start_emergency(self):
        decision = self.controller.update(100, "EMERGENCY")
        self.assertEqual(decision.state, State.COUNTDOWN)
        self.assertEqual(decision.deadline, 107)
        self.assertFalse(decision.shutdown_requested)

    def test_normal_monitoring(self):
        d = self.controller.update(100, "NORMAL")
        self.assertEqual(d.state, State.MONITORING)
        self.assertFalse(d.shutdown_requested)

    def test_warning_only(self):
        d = self.controller.update(100, "WARN")
        self.assertEqual(d.state, State.MONITORING)
        self.assertFalse(d.shutdown_requested)

    def test_emergency_countdown(self):
        self.start_emergency()

        d = self.controller.update(106.999, "EMERGENCY")
        self.assertFalse(d.shutdown_requested)

        d = self.controller.update(107, "EMERGENCY")
        self.assertTrue(d.shutdown_requested)

    def test_temperature_recovery_does_not_cancel(self):
        self.start_emergency()

        d = self.controller.update(103, "NORMAL")
        self.assertEqual(d.state, State.COUNTDOWN)
        self.assertEqual(d.deadline, 107)

        d = self.controller.update(107, "NORMAL")
        self.assertTrue(d.shutdown_requested)

    def test_yes_immediate_shutdown(self):
        self.start_emergency()

        d = self.controller.update(101, "EMERGENCY", "YES")
        self.assertTrue(d.shutdown_requested)

    def test_no_bounded_override(self):
        self.start_emergency()

        d = self.controller.update(103, "EMERGENCY", "NO")
        self.assertEqual(d.state, State.OVERRIDE)
        self.assertEqual(d.deadline, 133)
        self.assertFalse(d.shutdown_requested)

        d = self.controller.update(132.999, "NORMAL")
        self.assertFalse(d.shutdown_requested)

        d = self.controller.update(133, "NORMAL")
        self.assertTrue(d.shutdown_requested)

    def test_override_cannot_be_renewed(self):
        self.start_emergency()

        self.controller.update(103, "EMERGENCY", "NO")

        d = self.controller.update(120, "EMERGENCY", "NO")
        self.assertEqual(d.deadline, 133)

        d = self.controller.update(133, "EMERGENCY", "NO")
        self.assertTrue(d.shutdown_requested)

    def test_late_override_rejected(self):
        self.start_emergency()

        d = self.controller.update(107, "EMERGENCY", "NO")
        self.assertTrue(d.shutdown_requested)

    def test_immediate_critical_shutdown(self):
        d = self.controller.update(100, "CRITICAL")
        self.assertTrue(d.shutdown_requested)

    def test_critical_during_countdown(self):
        self.start_emergency()

        d = self.controller.update(101, "CRITICAL")
        self.assertTrue(d.shutdown_requested)

    def test_critical_during_override(self):
        self.start_emergency()

        self.controller.update(103, "EMERGENCY", "NO")

        d = self.controller.update(104, "CRITICAL", "NO")
        self.assertTrue(d.shutdown_requested)

    def test_sensor_loss_during_emergency(self):
        self.start_emergency()

        d = self.controller.update(102, "FAULT")
        self.assertEqual(d.state, State.COUNTDOWN)

        d = self.controller.update(107, "FAULT")
        self.assertTrue(d.shutdown_requested)

    def test_sensor_fault_without_emergency(self):
        d = self.controller.update(100, "FAULT")
        self.assertEqual(d.state, State.MONITORING)
        self.assertEqual(d.reason, "Required sensor fault")

    def test_gui_failure_does_not_cancel(self):
        self.start_emergency()

        # No operator response arrives from the GUI.
        d = self.controller.update(107, "EMERGENCY", None)
        self.assertTrue(d.shutdown_requested)

    def test_shutdown_state_is_irreversible(self):
        self.controller.update(100, "CRITICAL")

        d = self.controller.update(101, "NORMAL", "NO")
        self.assertTrue(d.shutdown_requested)

    def test_backwards_time_rejected(self):
        self.start_emergency()

        with self.assertRaises(ValueError):
            self.controller.update(99, "NORMAL")

    def test_premature_operator_response_ignored(self):
        d = self.controller.update(100, "EMERGENCY", "NO")
        self.assertEqual(d.state, State.COUNTDOWN)
        self.assertEqual(d.deadline, 107)

    def test_invalid_thermal_state(self):
        with self.assertRaises(ValueError):
            self.controller.update(100, "UNKNOWN")

    def test_nonfinite_time_rejected(self):
        with self.assertRaises(ValueError):
            self.controller.update(float("nan"), "NORMAL")

    def test_yes_during_override(self):
        self.start_emergency()

        self.controller.update(103, "EMERGENCY", "NO")

        d = self.controller.update(104, "EMERGENCY", "YES")
        self.assertTrue(d.shutdown_requested)


if __name__ == "__main__":
    unittest.main(verbosity=2)
