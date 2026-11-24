#!/usr/bin/env python3

"""Integrated supervisor runtime acceptance.

Real sensor sampling with isolated emergency injection.
No privileged operations or actual shutdown authority.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from thermal_guardian_recovery import RecoveryState
from thermal_guardian_latch import EmergencyLatch
from thermal_guardian_deadline import DeadlineRecord


def main():

    if os.geteuid() == 0:
        raise RuntimeError("Do not run as root")

    os.umask(0o077)

    directory = Path(tempfile.mkdtemp(
        prefix="tg-supervisor-runtime-"
    ))

    print(f"Evidence: {directory}", flush=True)

    config = ROOT / "examples/thermal-guardian-pots.json"

    recovery = RecoveryState(
        directory / "operating-state.json"
    )

    recovery.authorize_recovery(
        "Isolated supervisor runtime acceptance"
    )

    environment = os.environ.copy()
    environment.pop("NOTIFY_SOCKET", None)
    environment["PYTHONPATH"] = str(ROOT / "scripts")

    # Capture the supervisor's actual readiness messages.
    address = str(directory / "notify.sock")

    with socket.socket(
        socket.AF_UNIX, socket.SOCK_DGRAM
    ) as notifications:

        notifications.bind(address)
        notifications.settimeout(10)

        environment["NOTIFY_SOCKET"] = address

        # Use the actual sensor supervisor, initially without
        # emergency injection or executor connection.
        process = subprocess.Popen([
            sys.executable,
            "-u",
            str(ROOT / "scripts/thermal_guardian_supervisor.py"),
            "--config", str(config),
            "--state-dir", str(directory),
        ], env=environment)

        try:
            message = notifications.recv(4096).decode()

            assert "READY=1" in message
            assert recovery.status() == "ARMED"

            print("PASS: Actual supervisor ready")

            assert not EmergencyLatch(
                directory / "emergency-latch.json"
            ).blocks_computation()

            print("PASS: Initial emergency latch clear")

            for _ in range(3):

                message = notifications.recv(4096).decode()

                assert "WATCHDOG=1" in message

                print("PASS: Sensor-driven heartbeat")

            assert process.poll() is None
            assert recovery.status() == "ARMED"

            print("PASS: Persistent operating interlock")

        finally:
            if process.poll() is None:
                process.terminate()

            process.wait(timeout=5)

    assert recovery.status() == "ARMED"

    print("PASS: Unresolved termination retains interlock")
    print("PASS: Supervisor runtime acceptance")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
