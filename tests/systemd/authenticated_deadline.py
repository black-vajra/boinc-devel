#!/usr/bin/env python3

"""Integrated authenticated deadline acceptance.
Simulation only. No shutdown or hardware authority.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import threading

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from thermal_guardian_secure_executor import run as executor
from thermal_guardian_independent import run as guardian
from thermal_guardian_registration import DeadlineRegistration
from thermal_guardian_deadline import DeadlineRecord
from thermal_guardian_ipc import authorize_peer


def send(sock, kind, value, **extra):
    sock.send(json.dumps({
        "kind": kind,
        "value": value,
        **extra,
    }).encode())


def listener(path):
    sock = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
    )
    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_PASSCRED,
        1,
    )
    sock.bind(str(path))
    sock.listen(1)
    sock.settimeout(5)
    return sock


def connect(path):
    sock = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
    )
    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_PASSCRED,
        1,
    )
    sock.settimeout(5)

    expires = time.monotonic() + 5

    while True:
        try:
            sock.connect(str(path))
            return sock
        except (FileNotFoundError, ConnectionRefusedError):
            if time.monotonic() >= expires:
                sock.close()
                raise
            time.sleep(0.02)


def publish(path, record):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2))
    temporary.replace(path)


def guardian_main(directory, parent_pid):
    with listener(directory / "guardian.sock") as server:

        connection, _ = server.accept()

        with connection:

            authorize_peer(
                connection,
                os.getuid(),
                parent_pid,
            )

            def action(record):
                at = time.monotonic()

                publish(directory / "guardian-action.json", {
                    "at": at,
                    "deadline": record["deadline"],
                    "lateness": at - record["deadline"],
                    "pid": os.getpid(),
                    "simulated": True,
                })

                return 0

            return guardian(
                connection,
                expected_uid=os.getuid(),
                expected_pid=parent_pid,
                state_path=directory / "deadline.json",
                action=action,
            )


def executor_main(directory, parent_pid):

    child = subprocess.Popen([
        sys.executable,
        str(Path(__file__).resolve()),
        "guardian",
        str(directory),
        str(os.getpid()),
    ], start_new_session=True)

    try:
        with connect(directory / "guardian.sock") as registration:

            register = DeadlineRegistration(
                registration,
                os.getuid(),
                child.pid,
            )

            with listener(directory / "thermal.sock") as thermal_server:
                with listener(directory / "operator.sock") as operator_server:

                    thermal, _ = thermal_server.accept()
                    operator, _ = operator_server.accept()

                    with thermal, operator:

                        def action(decision):
                            publish(directory / "executor-action.json", {
                                "at": time.monotonic(),
                                "reason": decision.reason,
                                "simulated": True,
                            })

                        return executor(
                            thermal,
                            operator,
                            thermal_uid=os.getuid(),
                            thermal_pid=parent_pid,
                            operator_uid=os.getuid(),
                            operator_pid=parent_pid,
                            action=action,
                            deadline_registration=register,
                            countdown=7,
                            override=30,
                        )
    finally:
        # The acceptance harness manages guardian cleanup.
        # Do not terminate its established emergency timer.
        pass


def exercise(use_override):

    directory = Path(tempfile.mkdtemp(
        prefix="tg-authenticated-",
    ))

    child = subprocess.Popen([
        sys.executable,
        str(Path(__file__).resolve()),
        "executor",
        str(directory),
        str(os.getpid()),
    ], start_new_session=True)

    guardian_pid = None

    print(f"\nEvidence: {directory}", flush=True)

    try:
        with connect(directory / "thermal.sock") as thermal:
            with connect(directory / "operator.sock") as operator:

                authorize_peer(thermal, os.getuid(), child.pid)
                authorize_peer(operator, os.getuid(), child.pid)

                guardian_pid = int(
                    Path(
                        f"/proc/{child.pid}/task/{child.pid}/children"
                    ).read_text().split()[0]
                )

                send(thermal, "THERMAL", "EMERGENCY")

                event = json.loads(operator.recv(4096))

                assert event["state"] == "COUNTDOWN"

                store = DeadlineRecord(
                    directory / "deadline.json"
                )

                record = store.load()

                assert record["deadline"] == event["deadline"]

                print("PASS: Authenticated persistent registration")

                if use_override:

                    send(
                        operator,
                        "OPERATOR",
                        "NO",
                        token=event["token"],
                    )

                    event = json.loads(operator.recv(4096))
                    record = store.load()

                    assert event["state"] == "OVERRIDE"
                    assert record["override_used"]
                    assert record["deadline"] == event["deadline"]

                    print("PASS: Authorized override synchronized")

                    send(
                        operator,
                        "OPERATOR",
                        "NO",
                        token=event["token"],
                    )

                    time.sleep(0.1)

                    assert store.load() == record

                    print("PASS: Repeated override cannot renew")

                deadline = record["deadline"]

                fd = os.pidfd_open(child.pid)

                try:
                    remaining = deadline - time.monotonic()

                    assert remaining > 0.2

                    time.sleep(remaining - 0.1)

                    signal.pidfd_send_signal(
                        fd, signal.SIGSTOP
                    )

                    print("PASS: Executor deliberately frozen")

                    expires = deadline + 2
                    marker = directory / "guardian-action.json"

                    while not marker.exists():
                        if time.monotonic() >= expires:
                            raise RuntimeError(
                                "Independent action missing"
                            )
                        time.sleep(0.01)

                    result = json.loads(marker.read_text())

                    assert result["pid"] == guardian_pid
                    assert result["deadline"] == deadline
                    assert 0 <= result["lateness"] <= 0.25

                    assert not (
                        directory / "executor-action.json"
                    ).exists()

                    print("PASS: Independent guardian executed")
                    print(
                        "Deadline lateness: "
                        f"{result['lateness'] * 1000:.3f} ms"
                    )

                finally:
                    os.close(fd)

    finally:
        # These are isolated simulation processes,
        # never BOINC or science workers.
        if child.poll() is None:
            child.kill()

        child.wait(timeout=5)

        if guardian_pid is not None:
            try:
                os.kill(guardian_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    print("PASS: Integrated acceptance completed")


def main():

    if os.geteuid() == 0:
        raise RuntimeError("Do not run as root")

    os.umask(0o077)

    if len(sys.argv) > 1:
        directory = Path(sys.argv[2])
        parent_pid = int(sys.argv[3])

        if sys.argv[1] == "guardian":
            return guardian_main(directory, parent_pid)

        if sys.argv[1] == "executor":
            return executor_main(directory, parent_pid)

        raise ValueError("Unknown process role")

    exercise(False)
    exercise(True)

    print("\nPASS: Authenticated deadline integration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
