#!/usr/bin/env python3

"""Thermal Guardian local IPC validation.

No shutdown authority or hardware access.
"""

import array
import json
import os
import socket
import struct

from dataclasses import dataclass


MAX_PACKET = 4096

THERMAL_LEVELS = frozenset({
    "NORMAL",
    "WARN",
    "EMERGENCY",
    "CRITICAL",
    "FAULT",
})

OPERATOR_RESPONSES = frozenset({
    "YES",
    "NO",
})


class AuthorizationError(PermissionError):
    pass


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class PeerCredentials:
    pid: int
    uid: int
    gid: int


def peer_credentials(sock):
    size = struct.calcsize("3i")

    raw = sock.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        size,
    )

    pid, uid, gid = struct.unpack("3i", raw)

    return PeerCredentials(pid, uid, gid)


def authorize_peer(sock, expected_uid, expected_pid=None):
    credentials = peer_credentials(sock)

    if credentials.uid != expected_uid:
        raise AuthorizationError(
            "Unauthorized peer UID"
        )

    if (
        expected_pid is not None
        and credentials.pid != expected_pid
    ):
        raise AuthorizationError(
            "Unauthorized peer PID"
        )

    return credentials


def unique_fields(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ProtocolError("Duplicate message field")

        result[key] = value

    return result


def decode_message(packet, channel):
    if not isinstance(packet, bytes):
        raise ProtocolError("Invalid packet type")

    if not packet or len(packet) > MAX_PACKET:
        raise ProtocolError("Invalid packet length")

    try:
        message = json.loads(
            packet.decode("utf-8"),
            object_pairs_hook=unique_fields,
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ProtocolError("Malformed message") from error

    if not isinstance(message, dict):
        raise ProtocolError("Message must be an object")

    expected_fields = {"kind", "value"}

    if channel == "operator-session":
        expected_fields.add("token")

    if set(message) != expected_fields:
        raise ProtocolError("Unexpected message fields")

    if channel == "operator-session":
        token = message["token"]

        if (
            not isinstance(token, str)
            or len(token) != 64
            or any(c not in "0123456789abcdef" for c in token)
        ):
            raise ProtocolError("Invalid emergency token")

    kind = message["kind"]
    value = message["value"]

    if not isinstance(kind, str):
        raise ProtocolError("Invalid message kind")

    if not isinstance(value, str):
        raise ProtocolError("Invalid message value")

    if channel == "thermal":
        if kind != "THERMAL":
            raise AuthorizationError(
                "Thermal channel authority exceeded"
            )

        if value not in THERMAL_LEVELS:
            raise ProtocolError("Invalid thermal level")

    elif channel in ("operator", "operator-session"):
        if kind != "OPERATOR":
            raise AuthorizationError(
                "Operator channel authority exceeded"
            )

        if value not in OPERATOR_RESPONSES:
            raise ProtocolError("Invalid operator response")

    else:
        raise AuthorizationError("Unknown channel")

    return message


def receive_message(sock, channel, *, expected_peer=None):
    # Linux attaches credentials to actual packets,
    # including zero-length SOCK_SEQPACKET messages.
    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_PASSCRED,
        1,
    )

    packet, ancillary, flags, address = sock.recvmsg(
        MAX_PACKET,
        socket.CMSG_SPACE(struct.calcsize("3i")),
        socket.MSG_CMSG_CLOEXEC,
    )

    credentials_present = False
    credentials = None
    malformed_credentials = False
    unexpected_ancillary = False

    for level, kind, data in ancillary:

        if (
            level == socket.SOL_SOCKET
            and kind == socket.SCM_CREDENTIALS
        ):
            if (
                credentials_present
                or len(data) != struct.calcsize("3i")
            ):
                malformed_credentials = True
            else:
                credentials = PeerCredentials(
                    *struct.unpack("3i", data)
                )

            credentials_present = True

        elif (
            level == socket.SOL_SOCKET
            and kind == socket.SCM_RIGHTS
        ):
            # Close any descriptors received through
            # unsolicited ancillary data.
            descriptors = array.array("i")
            usable = len(data) - len(data) % descriptors.itemsize
            descriptors.frombytes(data[:usable])

            for fd in descriptors:
                os.close(fd)

            unexpected_ancillary = True

        else:
            unexpected_ancillary = True

    if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
        raise ProtocolError("Truncated message")

    if unexpected_ancillary:
        raise ProtocolError("Unexpected ancillary data")

    if not packet:
        if credentials_present:
            raise ProtocolError("Empty packet")

        raise EOFError("Peer disconnected")

    if malformed_credentials:
        raise ProtocolError("Malformed sender credentials")

    if expected_peer is not None:
        if credentials is None:
            raise AuthorizationError(
                "Missing sender credentials"
            )

        if credentials != expected_peer:
            raise AuthorizationError(
                "Message sender credentials mismatch"
            )

    return decode_message(packet, channel)
