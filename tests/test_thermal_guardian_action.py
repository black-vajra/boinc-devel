"""Test independent shutdown action execution.

Simulation only. No privileged commands or actual shutdown.
"""

import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "scripts"),
)

from thermal_guardian_executor import run


class ShutdownActionTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.marker = Path(self.temp.name) / "action.json"

        self.parent, self.child = socket.socketpair(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET,
        )

        self.addCleanup(self.parent.close)
        self.addCleanup(self.child.close)

        self.parent.settimeout(2)

        self.actions = []
        self.errors = []
        self.results = []

    def action(self, decision):
        self.actions.append(time.monotonic())

        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys,time;"
                    "from pathlib import Path;"
                    "Path(sys.argv[1]).write_text("
                    "json.dumps({'executed':True,"
                    "'at':time.monotonic(),"
                    "'reason':sys.argv[2]}))"
                ),
                str(self.marker),
                decision.reason,
            ],
            check=True,
            timeout=2,
        )

    def start_executor(self):
        def worker():
            try:
                self.results.append(
                    run(
                        self.child,
                        countdown=0.5,
                        override=0.75,
                        action=self.action,
                    )
                )
            except Exception as error:
                self.errors.append(error)

        self.thread = threading.Thread(
            target=worker,
            daemon=True,
        )

        self.thread.start()

    def send(self, kind, value):
        self.parent.send(json.dumps({
            "kind": kind,
            "value": value,
        }).encode())

    def receive(self):
        return json.loads(self.parent.recv(4096))

    def finish(self):
        self.thread.join(timeout=4)

        self.assertFalse(self.thread.is_alive())
        self.assertEqual(self.errors, [])
        self.assertEqual(self.results, [0])
        self.assertEqual(len(self.actions), 1)
        self.assertTrue(self.marker.is_file())

        record = json.loads(self.marker.read_text())
        self.assertTrue(record["executed"])

        return record

    def begin_emergency(self):
        self.start_executor()

        self.assertEqual(
            self.receive()["kind"], "READY"
        )

        self.send("THERMAL", "EMERGENCY")

        event = self.receive()
        self.assertEqual(event["state"], "COUNTDOWN")

        return event["deadline"]

    def test_normal_deadline(self):
        deadline = self.begin_emergency()
        record = self.finish()

        self.assertGreaterEqual(self.actions[0], deadline)
        self.assertLess(self.actions[0] - deadline, 0.25)

        self.assertEqual(
            record["reason"],
            "Emergency countdown expired",
        )

    def test_disconnected_reporting_peer(self):
        deadline = self.begin_emergency()
        self.parent.close()

        record = self.finish()

        self.assertGreaterEqual(self.actions[0], deadline)
        self.assertLess(self.actions[0] - deadline, 0.25)

        self.assertEqual(
            record["reason"],
            "Emergency countdown expired",
        )

    def test_saturated_notification_queue(self):
        self.child.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_SNDBUF,
            4096,
        )

        self.child.setblocking(False)

        packets = 0

        while True:
            try:
                self.child.send(b"x" * 1024)
                packets += 1
            except BlockingIOError:
                break

        self.assertGreater(packets, 0)

        self.start_executor()

        started = time.monotonic()
        self.send("THERMAL", "EMERGENCY")

        record = self.finish()
        elapsed = self.actions[0] - started

        self.assertGreaterEqual(elapsed, 0.5)
        self.assertLess(elapsed, 0.75)

        self.assertEqual(
            record["reason"],
            "Emergency countdown expired",
        )

    def test_absolute_critical_action(self):
        self.begin_emergency()
        self.send("THERMAL", "CRITICAL")

        record = self.finish()

        self.assertEqual(
            record["reason"],
            "Absolute critical temperature",
        )

    def test_operator_immediate_action(self):
        deadline = self.begin_emergency()
        self.send("OPERATOR", "YES")

        record = self.finish()

        self.assertLess(self.actions[0], deadline)

        self.assertEqual(
            record["reason"],
            "Operator requested immediate shutdown",
        )

    def test_override_expiration(self):
        self.begin_emergency()
        self.send("OPERATOR", "NO")

        event = self.receive()
        self.assertEqual(event["state"], "OVERRIDE")

        deadline = event["deadline"]
        record = self.finish()

        self.assertGreaterEqual(self.actions[0], deadline)
        self.assertLess(self.actions[0] - deadline, 0.25)

        self.assertEqual(
            record["reason"],
            "Manual intervention period expired",
        )


if __name__ == "__main__":
    unittest.main()
