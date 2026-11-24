#!/usr/bin/env python3
"""Regression tests for Thermal Guardian executor completion reporting."""

import socket
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from thermal_guardian_ipc import decode_message, ProtocolError
from thermal_guardian_secure_executor import report_action_result


class ActionCompletionTests(unittest.TestCase):
    def setUp(self):
        self.receiver, self.sender = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_SEQPACKET
        )

    def tearDown(self):
        self.receiver.close()
        self.sender.close()

    def receive(self):
        return decode_message(
            self.receiver.recv(4096),
            "executor-status",
        )

    def test_accepted_action_reports_completion(self):
        status = report_action_result(
            self.sender, lambda decision: None, object()
        )
        self.assertEqual(status, 0)
        self.assertEqual(
            self.receive(),
            {"kind": "ACTION_COMPLETE", "value": "ACCEPTED"},
        )

    def test_rejected_action_reports_failure(self):
        status = report_action_result(
            self.sender,
            lambda decision: SimpleNamespace(accepted=False),
            object(),
        )
        self.assertEqual(status, 3)
        self.assertEqual(
            self.receive(),
            {"kind": "ACTION_FAILED", "value": "Action rejected"},
        )

    def test_exception_reports_failure(self):
        def fail(_decision):
            raise RuntimeError("fixture failure")

        status = report_action_result(self.sender, fail, object())
        self.assertEqual(status, 3)
        message = self.receive()
        self.assertEqual(message["kind"], "ACTION_FAILED")
        self.assertIn("fixture failure", message["value"])

    def test_unknown_status_kind_is_rejected(self):
        with self.assertRaises(PermissionError):
            decode_message(
                b'{"kind":"THERMAL","value":"NORMAL"}',
                "executor-status",
            )

    def test_invalid_completion_value_is_rejected(self):
        with self.assertRaises(ProtocolError):
            decode_message(
                b'{"kind":"ACTION_COMPLETE","value":"MAYBE"}',
                "executor-status",
            )

    def test_send_failure_does_not_invalidate_successful_action(self):
        self.receiver.close()
        executed = []
        status = report_action_result(
            self.sender,
            lambda decision: executed.append(True),
            object(),
        )
        self.assertEqual(executed, [True])
        self.assertEqual(status, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
