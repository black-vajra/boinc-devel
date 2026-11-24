"""Local IPC authentication and protocol tests."""

import json
import os
import socket
import sys
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
    decode_message,
    peer_credentials,
    receive_message,
)


def packet(kind, value):
    return json.dumps({
        "kind": kind,
        "value": value,
    }).encode()


class IPCTests(unittest.TestCase):

    def setUp(self):
        self.a, self.b = socket.socketpair(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET,
        )

        self.a.settimeout(2)
        self.b.settimeout(2)

        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)

    def test_peer_credentials(self):
        peer = peer_credentials(self.a)

        self.assertEqual(peer.uid, os.getuid())
        self.assertEqual(peer.gid, os.getgid())
        self.assertEqual(peer.pid, os.getpid())

    def test_authorized_uid(self):
        peer = authorize_peer(self.a, os.getuid())
        self.assertEqual(peer.uid, os.getuid())

    def test_wrong_uid_rejected(self):
        with self.assertRaises(AuthorizationError):
            authorize_peer(self.a, os.getuid() + 1)

    def test_authorized_pid(self):
        authorize_peer(
            self.a,
            os.getuid(),
            os.getpid(),
        )

    def test_wrong_pid_rejected(self):
        with self.assertRaises(AuthorizationError):
            authorize_peer(
                self.a,
                os.getuid(),
                os.getpid() + 1,
            )

    def test_valid_thermal_levels(self):
        for level in (
            "NORMAL", "WARN", "EMERGENCY",
            "CRITICAL", "FAULT",
        ):
            with self.subTest(level=level):
                message = decode_message(
                    packet("THERMAL", level),
                    "thermal",
                )

                self.assertEqual(message["value"], level)

    def test_valid_operator_responses(self):
        for response in ("YES", "NO"):
            message = decode_message(
                packet("OPERATOR", response),
                "operator",
            )

            self.assertEqual(
                message["value"], response
            )

    def test_operator_cannot_inject_temperature(self):
        with self.assertRaises(AuthorizationError):
            decode_message(
                packet("THERMAL", "CRITICAL"),
                "operator",
            )

    def test_thermal_channel_cannot_override(self):
        with self.assertRaises(AuthorizationError):
            decode_message(
                packet("OPERATOR", "NO"),
                "thermal",
            )

    def test_invalid_thermal_level(self):
        with self.assertRaises(ProtocolError):
            decode_message(
                packet("THERMAL", "UNKNOWN"),
                "thermal",
            )

    def test_invalid_operator_response(self):
        with self.assertRaises(ProtocolError):
            decode_message(
                packet("OPERATOR", "CANCEL"),
                "operator",
            )

    def test_unknown_channel(self):
        with self.assertRaises(AuthorizationError):
            decode_message(
                packet("OPERATOR", "YES"),
                "diagnostics",
            )

    def test_invalid_json(self):
        with self.assertRaises(ProtocolError):
            decode_message(b"not-json", "thermal")

    def test_empty_message(self):
        with self.assertRaises(ProtocolError):
            decode_message(b"", "thermal")

    def test_non_object_message(self):
        with self.assertRaises(ProtocolError):
            decode_message(b'["THERMAL"]', "thermal")

    def test_additional_fields(self):
        with self.assertRaises(ProtocolError):
            decode_message(
                b'{"kind":"THERMAL","value":"NORMAL",'
                b'"command":"poweroff"}',
                "thermal",
            )

    def test_duplicate_fields(self):
        with self.assertRaises(ProtocolError):
            decode_message(
                b'{"kind":"THERMAL","value":"NORMAL",'
                b'"value":"CRITICAL"}',
                "thermal",
            )

    def test_invalid_value_type(self):
        with self.assertRaises(ProtocolError):
            decode_message(
                packet("THERMAL", ["CRITICAL"]),
                "thermal",
            )

    def test_oversized_packet(self):
        with self.assertRaises(ProtocolError):
            decode_message(b"x" * 4097, "thermal")

    def test_invalid_utf8(self):
        with self.assertRaises(ProtocolError):
            decode_message(b"\xff", "thermal")

    def test_socket_message(self):
        self.b.send(packet("THERMAL", "EMERGENCY"))

        result = receive_message(self.a, "thermal")

        self.assertEqual(
            result["value"], "EMERGENCY"
        )

    def test_socket_truncation(self):
        self.b.send(b"x" * 8192)

        with self.assertRaises(ProtocolError):
            receive_message(self.a, "thermal")

    def test_disconnected_peer(self):
        self.b.close()

        with self.assertRaises(EOFError):
            receive_message(self.a, "thermal")


if __name__ == "__main__":
    unittest.main()
