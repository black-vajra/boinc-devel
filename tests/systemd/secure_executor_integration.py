#!/usr/bin/env python3

"""Authenticated systemd integration fixture.

Simulation only. No poweroff or privileged operations.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from thermal_guardian_secure_executor import run
from thermal_guardian_ipc import authorize_peer


def main_pid(unit):
    return int(subprocess.check_output(
        [
            "systemctl", "--user", "show",
            unit, "-p", "MainPID", "--value",
        ],
        text=True,
        env={k: v for k, v in os.environ.items()
             if k != "NOTIFY_SOCKET"},
        timeout=2,
    ).strip())


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Development fixture cannot run as root")

    directory = Path(sys.argv[1])
    address = directory / "executor.sock"

    os.umask(0o077)

    def action(decision):
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys,time;"
                    "from pathlib import Path;"
                    "Path(sys.argv[1]).write_text("
                    "json.dumps(dict(executed=True,"
                    "at=time.monotonic(),reason=sys.argv[2])))"
                ),
                str(directory / "action.json"),
                decision.reason,
            ],
            timeout=2,
            check=True,
        )

        print("PASS: Independent simulated action executed",
              flush=True)

    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
    ) as listener:

        listener.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_PASSCRED,
            1,
        )

        listener.bind(str(address))
        listener.listen(1)
        listener.settimeout(15)

        print("PASS: Thermal transport listening", flush=True)

        connection, _ = listener.accept()

        with connection:
            expected_pid = main_pid(
                "tg-test-secure-supervisor.service"
            )

            if expected_pid <= 0:
                raise RuntimeError("Supervisor PID unavailable")

            peer = authorize_peer(
                connection,
                os.getuid(),
                expected_pid,
            )

            print(
                f"PASS: Supervisor authenticated: {peer}",
                flush=True,
            )

            operator_rx, operator_tx = socket.socketpair(
                socket.AF_UNIX,
                socket.SOCK_SEQPACKET,
            )

            with operator_rx, operator_tx:

                def observe_emergency():
                    try:
                        event = json.loads(
                            operator_tx.recv(4096)
                        )

                        if event["kind"] == "EMERGENCY_SESSION":
                            evidence = {
                                "deadline": event["deadline"],
                                "state": event["state"],
                            }

                            temporary = directory / "deadline.tmp"

                            temporary.write_text(
                                json.dumps(evidence)
                            )

                            temporary.replace(
                                directory / "deadline.json"
                            )

                    except Exception as error:
                        print(
                            f"Evidence observer: {error}",
                            flush=True,
                        )

                threading.Thread(
                    target=observe_emergency,
                    daemon=True,
                ).start()

                return run(
                    connection,
                    operator_rx,
                    thermal_uid=os.getuid(),
                    thermal_pid=expected_pid,
                    operator_uid=os.getuid(),
                    operator_pid=os.getpid(),
                    action=action,
                    notify_address=os.environ["NOTIFY_SOCKET"],
                )


if __name__ == "__main__":
    raise SystemExit(main())
