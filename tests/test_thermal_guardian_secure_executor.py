"""Authenticated emergency executor integration tests."""

import json
import os
import socket
import subprocess
import tempfile
import sys
import threading
import time
import unittest

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "scripts"),
)

from thermal_guardian_ipc import (
    AuthorizationError,
    ProtocolError,
    authorize_peer,
    receive_message,
)
from thermal_guardian_secure_executor import run


class SecureExecutorTests(unittest.TestCase):

    def setUp(self):
        self.thermal_rx, self.thermal_tx = socket.socketpair(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET,
        )

        self.operator_rx, self.operator_tx = socket.socketpair(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET,
        )

        for sock in (
            self.thermal_rx,
            self.thermal_tx,
            self.operator_rx,
            self.operator_tx,
        ):
            self.addCleanup(sock.close)

        for receiver in (
            self.thermal_rx,
            self.operator_rx,
        ):
            receiver.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_PASSCRED,
                1,
            )

        self.token = None
        self.actions = []
        self.results = []
        self.errors = []

    def action(self, decision):
        self.actions.append(
            (time.monotonic(), decision.reason)
        )

    def start(self, **options):
        settings = {
            "thermal_uid": os.getuid(),
            "operator_uid": os.getuid(),
            "action": self.action,
            "countdown": 1,
            "override": 2,
        }

        settings.update(options)

        def worker():
            try:
                result = run(
                    self.thermal_rx,
                    self.operator_rx,
                    **settings,
                )

                self.results.append(result)

            except Exception as error:
                self.errors.append(error)

        self.thread = threading.Thread(
            target=worker,
            daemon=True,
        )

        self.thread.start()

    def send(self, sock, kind, value):
        sock.send(json.dumps({
            "kind": kind,
            "value": value,
        }).encode())

    def thermal(self, value):
        self.send(
            self.thermal_tx,
            "THERMAL",
            value,
        )

    def receive_session(self):
        self.operator_tx.settimeout(3)

        event = json.loads(
            self.operator_tx.recv(4096)
        )

        self.assertEqual(
            event["kind"],
            "EMERGENCY_SESSION",
        )

        self.assertEqual(len(event["token"]), 64)

        self.token = event["token"]

        return event

    def operator(self, value):
        if self.token is None:
            self.receive_session()

        self.operator_tx.send(json.dumps({
            "kind": "OPERATOR",
            "value": value,
            "token": self.token,
        }).encode())

    def finish(self, timeout=5):
        self.thread.join(timeout)

        self.assertFalse(
            self.thread.is_alive(),
            "Executor failed to terminate",
        )

        self.assertFalse(self.errors)

    def test_normal_countdown(self):
        self.start()

        started = time.monotonic()

        self.thermal("EMERGENCY")

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(len(self.actions), 1)

        elapsed = self.actions[0][0] - started

        self.assertGreaterEqual(elapsed, 0.99)
        self.assertLess(elapsed, 1.30)

    def test_unauthorized_thermal_uid(self):
        with self.assertRaises(AuthorizationError):
            run(
                self.thermal_rx,
                self.operator_rx,
                thermal_uid=os.getuid() + 1,
                operator_uid=os.getuid(),
                action=self.action,
            )

        self.assertFalse(self.actions)

    def test_unauthorized_operator_uid(self):
        with self.assertRaises(AuthorizationError):
            run(
                self.thermal_rx,
                self.operator_rx,
                thermal_uid=os.getuid(),
                operator_uid=os.getuid() + 1,
                action=self.action,
            )

        self.assertFalse(self.actions)

    def test_operator_cannot_inject_critical(self):
        self.start()

        self.send(
            self.operator_tx,
            "THERMAL",
            "CRITICAL",
        )

        time.sleep(0.10)

        self.assertFalse(self.actions)

        self.thermal_tx.close()

        self.finish()

        self.assertEqual(self.results, [2])

    def test_operator_yes_without_emergency(self):
        self.start()

        self.send(self.operator_tx, "OPERATOR", "YES")

        time.sleep(0.10)

        self.assertFalse(self.actions)

        self.thermal_tx.close()

        self.finish()

        self.assertEqual(self.results, [2])

    def test_thermal_channel_cannot_override(self):
        self.start()

        started = time.monotonic()

        self.thermal("EMERGENCY")

        self.send(
            self.thermal_tx,
            "OPERATOR",
            "NO",
        )

        self.finish()

        elapsed = self.actions[0][0] - started

        self.assertLess(elapsed, 1.30)
        self.assertEqual(self.results, [0])

    def test_malformed_packets_during_emergency(self):
        self.start()

        self.thermal("EMERGENCY")

        self.thermal_tx.send(b"not-json")
        self.operator_tx.send(b"\xff")
        self.operator_tx.send(b"x" * 8192)

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(len(self.actions), 1)

    def test_supervisor_disconnection(self):
        self.start()

        self.thermal("EMERGENCY")
        self.thermal_tx.close()

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(len(self.actions), 1)

    def test_operator_disconnection(self):
        self.start()

        self.thermal("EMERGENCY")
        self.operator_tx.close()

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(len(self.actions), 1)

    def test_critical_escalation_during_override(self):
        self.start()

        self.thermal("EMERGENCY")

        time.sleep(0.10)

        self.operator("NO")

        time.sleep(0.10)

        self.assertFalse(self.actions)

        started = time.monotonic()

        self.thermal("CRITICAL")

        self.finish()

        self.assertLess(
            self.actions[0][0] - started,
            0.30,
        )

        self.assertEqual(self.results, [0])

    def test_repeated_override_not_renewed(self):
        self.start()

        self.thermal("EMERGENCY")

        time.sleep(0.10)

        started = time.monotonic()

        self.operator("NO")

        for _ in range(5):
            time.sleep(0.20)
            self.operator("NO")

        self.finish()

        elapsed = self.actions[0][0] - started

        self.assertGreaterEqual(elapsed, 1.95)
        self.assertLess(elapsed, 2.30)

    def test_message_flood_does_not_delay_deadline(self):
        self.start()

        started = time.monotonic()

        self.thermal("EMERGENCY")

        self.operator_tx.setblocking(False)

        until = started + 1.20

        while time.monotonic() < until:
            try:
                self.operator_tx.send(b"invalid")
            except BlockingIOError:
                time.sleep(0.001)

        self.finish()

        elapsed = self.actions[0][0] - started

        self.assertGreaterEqual(elapsed, 0.99)
        self.assertLess(elapsed, 1.30)

    def test_shutdown_action_failure(self):
        def failed_action(decision):
            raise RuntimeError("Simulated backend failure")

        self.start(action=failed_action)

        self.thermal("CRITICAL")

        self.finish()

        self.assertEqual(self.results, [3])



    def test_thermal_channel_survives_authority_violation(self):
        self.start()

        self.send(self.thermal_tx, "OPERATOR", "NO")
        self.thermal("CRITICAL")

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(len(self.actions), 1)
        self.assertEqual(
            self.actions[0][1],
            "Absolute critical temperature",
        )

    def test_operator_channel_survives_authority_violation(self):
        self.start(countdown=2)

        self.send(self.operator_tx, "THERMAL", "CRITICAL")

        time.sleep(0.10)

        self.thermal("EMERGENCY")

        time.sleep(0.10)

        self.operator("YES")

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Operator requested immediate shutdown",
        )

    def test_empty_thermal_packet_preserves_channel(self):
        self.start()

        self.thermal_tx.send(b"")
        self.thermal("CRITICAL")

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Absolute critical temperature",
        )

    def test_empty_packet_during_countdown_preserves_escalation(self):
        self.start(countdown=2)

        self.thermal("EMERGENCY")
        self.thermal_tx.send(b"")
        self.thermal("CRITICAL")

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Absolute critical temperature",
        )



    def test_queued_unauthorized_no_cannot_override(self):
        self.send(self.operator_tx, "OPERATOR", "NO")
        self.thermal("EMERGENCY")

        self.start()

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Emergency countdown expired",
        )

    def test_queued_unauthorized_yes_cannot_shutdown(self):
        self.send(self.operator_tx, "OPERATOR", "YES")
        self.thermal("EMERGENCY")

        self.start()

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Emergency countdown expired",
        )

    def test_wrong_token_cannot_override(self):
        self.start()

        self.thermal("EMERGENCY")
        session = self.receive_session()

        wrong = (
            "0" if session["token"][0] != "0" else "1"
        ) + session["token"][1:]

        self.operator_tx.send(json.dumps({
            "kind": "OPERATOR",
            "value": "NO",
            "token": wrong,
        }).encode())

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Emergency countdown expired",
        )

    def test_valid_token_authorizes_immediate_shutdown(self):
        self.start(countdown=2)

        self.thermal("EMERGENCY")
        self.receive_session()

        self.operator("YES")

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Operator requested immediate shutdown",
        )

    def test_override_publishes_authoritative_deadline(self):
        self.start(countdown=1, override=2)

        self.thermal("EMERGENCY")
        initial = self.receive_session()

        self.operator("NO")
        updated = self.receive_session()

        self.assertEqual(updated["state"], "OVERRIDE")
        self.assertEqual(
            initial["token"],
            updated["token"],
        )
        self.assertGreater(
            updated["deadline"],
            initial["deadline"],
        )

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Manual intervention period expired",
        )



    def child_send(self, sock, message):
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import socket,sys;"
                    "s=socket.socket(fileno=int(sys.argv[1]));"
                    "s.send(sys.argv[2].encode());"
                    "s.close()"
                ),
                str(sock.fileno()),
                json.dumps(message),
            ],
            pass_fds=(sock.fileno(),),
            timeout=3,
            check=True,
        )

    def test_inherited_thermal_descriptor_rejected(self):
        self.child_send(
            self.thermal_tx,
            {"kind": "THERMAL", "value": "CRITICAL"},
        )

        self.thermal("EMERGENCY")
        self.start()

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Emergency countdown expired",
        )

    def test_inherited_operator_descriptor_rejected(self):
        self.start(countdown=2)

        self.thermal("EMERGENCY")
        self.receive_session()

        self.child_send(
            self.operator_tx,
            {
                "kind": "OPERATOR",
                "value": "NO",
                "token": self.token,
            },
        )

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Emergency countdown expired",
        )

    def test_legitimate_sender_survives_impersonation(self):
        self.child_send(
            self.thermal_tx,
            {"kind": "THERMAL", "value": "NORMAL"},
        )

        self.thermal("CRITICAL")
        self.start()

        self.finish()

        self.assertEqual(self.results, [0])
        self.assertEqual(
            self.actions[0][1],
            "Absolute critical temperature",
        )

    def test_real_cross_process_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            address = str(Path(directory) / "control.sock")

            with socket.socket(
                socket.AF_UNIX,
                socket.SOCK_SEQPACKET,
            ) as listener:

                listener.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_PASSCRED,
                    1,
                )

                listener.bind(address)
                listener.listen(1)
                listener.settimeout(3)

                with subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        (
                            "import socket,sys;"
                            "s=socket.socket(socket.AF_UNIX,"
                            "socket.SOCK_SEQPACKET);"
                            "s.connect(sys.argv[1]);"
                            "s.send(b'{\"kind\":\"THERMAL\","
                            "\"value\":\"NORMAL\"}');"
                            "s.close()"
                        ),
                        address,
                        json.dumps({
                            "kind": "THERMAL",
                            "value": "NORMAL",
                        }),
                    ]
                ) as child:

                    connection, _ = listener.accept()

                    with connection:
                        connection.settimeout(3)

                        peer = authorize_peer(
                            connection,
                            os.getuid(),
                            child.pid,
                        )

                        self.assertNotEqual(
                            peer.pid, os.getpid()
                        )

                        with self.assertRaises(
                            AuthorizationError
                        ):
                            authorize_peer(
                                connection,
                                os.getuid(),
                                os.getpid(),
                            )

                        message = receive_message(
                            connection,
                            "thermal",
                            expected_peer=peer,
                        )

                        self.assertEqual(
                            message["value"],
                            "NORMAL",
                        )

                    self.assertEqual(
                        child.wait(timeout=3), 0
                    )

    def test_unsolicited_descriptor_rejected_without_leak(self):
        import array

        peer = authorize_peer(
            self.thermal_rx,
            os.getuid(),
            os.getpid(),
        )

        fd = os.open("/dev/null", os.O_RDONLY)

        try:
            before = len(os.listdir("/proc/self/fd"))

            self.thermal_tx.sendmsg(
                [b'{"kind":"THERMAL","value":"NORMAL"}'],
                [
                    (
                        socket.SOL_SOCKET,
                        socket.SCM_RIGHTS,
                        array.array("i", [fd]),
                    )
                ],
            )

            with self.assertRaises(ProtocolError):
                receive_message(
                    self.thermal_rx,
                    "thermal",
                    expected_peer=peer,
                )

            after = len(os.listdir("/proc/self/fd"))

            self.assertEqual(before, after)

            self.thermal("NORMAL")

            message = receive_message(
                self.thermal_rx,
                "thermal",
                expected_peer=peer,
            )

            self.assertEqual(message["value"], "NORMAL")

        finally:
            os.close(fd)


if __name__ == "__main__":
    unittest.main()
