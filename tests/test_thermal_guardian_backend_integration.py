"""Executor and shutdown backend integration.

Harmless commands only. No actual shutdown.
"""

import json
import socket
import sys
import threading
import unittest

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "scripts"),
)

from thermal_guardian_executor import run
from thermal_guardian_shutdown import ShutdownBackend


TRUE = ("/usr/bin/true",)
FALSE = ("/usr/bin/false",)
SLEEP = ("/usr/bin/sleep", "10")


class BackendIntegrationTests(unittest.TestCase):

    def exercise(self, action):
        parent, child = socket.socketpair(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET,
        )

        results = []
        errors = []

        def worker():
            try:
                results.append(
                    run(
                        child,
                        countdown=0.2,
                        override=0.3,
                        action=action,
                    )
                )
            except Exception as error:
                errors.append(error)

        with parent, child:
            parent.settimeout(4)

            thread = threading.Thread(
                target=worker,
                daemon=True,
            )

            thread.start()

            ready = json.loads(parent.recv(4096))
            self.assertEqual(ready["kind"], "READY")

            parent.send(json.dumps({
                "kind": "THERMAL",
                "value": "EMERGENCY",
            }).encode())

            state = json.loads(parent.recv(4096))
            self.assertEqual(state["state"], "COUNTDOWN")

            event = json.loads(parent.recv(4096))

            thread.join(timeout=4)

            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 1)

            return event, results[0]

    def test_primary_accepted(self):
        event, code = self.exercise(
            ShutdownBackend(
                primary=TRUE,
                fallback=FALSE,
            )
        )

        self.assertEqual(code, 0)
        self.assertEqual(
            event["kind"], "SIMULATED_SHUTDOWN"
        )

    def test_fallback_accepted(self):
        event, code = self.exercise(
            ShutdownBackend(
                primary=FALSE,
                fallback=TRUE,
            )
        )

        self.assertEqual(code, 0)
        self.assertEqual(
            event["kind"], "SIMULATED_SHUTDOWN"
        )

    def test_both_commands_failed(self):
        event, code = self.exercise(
            ShutdownBackend(
                primary=FALSE,
                fallback=FALSE,
            )
        )

        self.assertEqual(code, 3)
        self.assertEqual(
            event["kind"], "SHUTDOWN_FAILED"
        )

    def test_primary_timeout_fallback_accepted(self):
        event, code = self.exercise(
            ShutdownBackend(
                primary=SLEEP,
                fallback=TRUE,
                primary_timeout=0.2,
            )
        )

        self.assertEqual(code, 0)
        self.assertEqual(
            event["kind"], "SIMULATED_SHUTDOWN"
        )

    def test_both_commands_timeout(self):
        event, code = self.exercise(
            ShutdownBackend(
                primary=SLEEP,
                fallback=SLEEP,
                primary_timeout=0.2,
                fallback_timeout=0.2,
            )
        )

        self.assertEqual(code, 3)
        self.assertEqual(
            event["kind"], "SHUTDOWN_FAILED"
        )

    def test_unexpected_backend_exception(self):
        def broken_action(decision):
            raise RuntimeError("Synthetic backend failure")

        event, code = self.exercise(broken_action)

        self.assertEqual(code, 3)
        self.assertEqual(
            event["kind"], "SHUTDOWN_FAILED"
        )
        self.assertIn(
            "Synthetic backend failure",
            event["error"],
        )


if __name__ == "__main__":
    unittest.main()
