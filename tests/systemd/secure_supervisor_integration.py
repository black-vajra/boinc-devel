#!/usr/bin/env python3

"""Authenticated sensor supervisor integration fixture.

Real sensor readings; synthetic emergency trigger.
No privileged operations.
"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from thermal_guardian_supervisor import notify, sample
from thermal_guardian import validate_config
from thermal_guardian_recovery import RecoveryState
from thermal_guardian_ipc import authorize_peer


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Development fixture cannot run as root")

    directory = Path(sys.argv[1])

    config = json.loads(
        (
            ROOT / "examples/thermal-guardian-pots.json"
        ).read_text()
    )

    validate_config(config)

    recovery = RecoveryState(
        directory / "operating-state.json"
    )

    if recovery.status() != "CLEAN":
        raise RuntimeError("Recovery authorization required")

    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
    ) as connection:

        connection.settimeout(2)

        expires = time.monotonic() + 10

        while True:
            try:
                connection.connect(
                    str(directory / "executor.sock")
                )
                break

            except (FileNotFoundError, ConnectionRefusedError):
                if time.monotonic() >= expires:
                    raise

                time.sleep(0.1)

        expected_pid = int(subprocess.check_output(
            [
                "systemctl", "--user", "show",
                "tg-test-secure-executor.service",
                "-p", "MainPID", "--value",
            ],
            text=True,
            env={k: v for k, v in os.environ.items()
                 if k != "NOTIFY_SOCKET"},
            timeout=2,
        ).strip())

        if expected_pid <= 0:
            raise RuntimeError("Executor PID unavailable")

        authorize_peer(
            connection,
            os.getuid(),
            expected_pid,
        )

        event = json.loads(connection.recv(4096))

        if event != {"kind": "READY"}:
            raise RuntimeError("Invalid executor readiness")

        print("PASS: Authenticated executor READY",
              flush=True)

        snapshot = sample(config)

        if snapshot["faults"] or snapshot["level"] != "NORMAL":
            raise RuntimeError("Unsafe initial sensor state")

        recovery.arm()

        if recovery.status() != "ARMED":
            raise RuntimeError("Persistent arming failed")

        notify(
            "READY=1" + chr(10) +
            "STATUS=Authenticated supervisor armed"
        )

        print("PASS: Supervisor READY", flush=True)

        while True:
            snapshot = sample(config)

            level = snapshot["level"]

            if (directory / "trigger").exists():
                if level not in ("EMERGENCY", "CRITICAL"):
                    level = "EMERGENCY"

            connection.send(json.dumps({
                "kind": "THERMAL",
                "value": level,
            }).encode())

            if snapshot["faults"]:
                raise RuntimeError("Required sensor fault")

            if level in ("EMERGENCY", "CRITICAL"):
                recovery.emergency(
                    f"Integration emergency: {level}"
                )

                print(
                    "PASS: Emergency delivered to executor",
                    flush=True,
                )

                while True:
                    notify("WATCHDOG=1")
                    time.sleep(0.25)

            notify("WATCHDOG=1")

            time.sleep(0.25)


if __name__ == "__main__":
    raise SystemExit(main())
