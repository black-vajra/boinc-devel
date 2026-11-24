#!/usr/bin/env python3

"""Thermal Guardian integration harness.

SIMULATION ONLY.
No poweroff commands or privileged operations.
"""

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time

from pathlib import Path

from thermal_guardian_latch import EmergencyLatch


SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
PYTHON = sys.executable


def send(sock, kind, value):
    sock.send(json.dumps({
        "kind": kind,
        "value": value,
    }).encode())


def receive(sock):
    raw = sock.recv(4096)

    if not raw:
        raise RuntimeError("Executor disconnected")

    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--no-gui", action="store_true"
    )

    parser.add_argument(
        "--stall-worker", action="store_true"
    )

    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(
        prefix="thermal-integration-"
    ))

    latch_path = workdir / "emergency-latch.json"

    print("=== THERMAL EMERGENCY SIMULATION ===", flush=True)
    print("Shutdown authority: DISABLED", flush=True)
    print(f"Evidence directory: {workdir}", flush=True)

    parent, child = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
    )

    parent.settimeout(2)

    processes = []
    executor = None

    try:
        executor = subprocess.Popen(
            [
                PYTHON,
                str(SCRIPTS / "thermal_guardian_executor.py"),
                "--fd",
                str(child.fileno()),
            ],
            pass_fds=(child.fileno(),),
        )

        processes.append(executor)
        child.close()

        ready = receive(parent)

        if ready.get("kind") != "READY":
            raise RuntimeError("Executor not ready")

        print("PASS: Independent executor ready", flush=True)

        send(parent, "THERMAL", "EMERGENCY")

        event = receive(parent)

        if event.get("state") != "COUNTDOWN":
            raise RuntimeError("Countdown not established")

        deadline = event["deadline"]

        print(
            "PASS: Authoritative deadline established",
            flush=True,
        )

        # Separate persistence worker. Filesystem operations
        # cannot block the independent executor.
        latch_worker = subprocess.Popen([
            PYTHON,
            "-c",
            (
                "import sys; "
                "from thermal_guardian_latch import EmergencyLatch; "
                "print(EmergencyLatch(sys.argv[1]).create("
                "'GPU junction',101,100,'EMERGENCY',"
                "'Integration simulation'),flush=True)"
            ),
            str(latch_path),
        ], cwd=SCRIPTS)

        processes.append(latch_worker)

        if args.stall_worker:
            stalled = subprocess.Popen([
                PYTHON,
                "-c",
                "import time; time.sleep(120)",
            ])

            processes.append(stalled)

            print(
                "TEST: Auxiliary worker deliberately stalled",
                flush=True,
            )

        ui = None

        if not args.no_gui:
            ui = subprocess.Popen([
                PYTHON,
                str(SCRIPTS / "thermal_guardian_ui.py"),
                "--sensor", "GPU junction",
                "--temperature", "101",
                "--threshold", "100",
                "--seconds", "7",
                "--alarm",
                str(ROOT / "assets/sounds/thermal-emergency.wav"),
            ])

            processes.append(ui)

        parent.settimeout(0.05)

        response_sent = False
        expected_deadline = deadline
        hard_timeout = time.monotonic() + 45

        while time.monotonic() < hard_timeout:

            if ui is not None and not response_sent:
                code = ui.poll()

                if code is not None:
                    response_sent = True

                    if code == 10:
                        send(parent, "OPERATOR", "YES")
                        print("Operator selected YES", flush=True)

                    elif code == 20:
                        send(parent, "OPERATOR", "NO")
                        print("Operator selected NO", flush=True)

                    else:
                        print(
                            f"UI exit {code}; deadline unchanged",
                            flush=True,
                        )

            try:
                event = receive(parent)
            except socket.timeout:
                continue

            if event["kind"] == "STATE":

                print(
                    f"Executor state: {event['state']}",
                    flush=True,
                )

                if event.get("deadline") is not None:
                    expected_deadline = event["deadline"]

            elif event["kind"] == "SIMULATED_SHUTDOWN":

                delta = event["at"] - expected_deadline

                print(
                    "SIMULATED POWEROFF",
                    flush=True,
                )

                print(
                    f"Reason: {event['reason']}",
                    flush=True,
                )

                print(
                    f"Deadline delta: {delta:+.6f}s",
                    flush=True,
                )

                reason = event["reason"]

                if "expired" in reason.lower():
                    if not 0 <= delta < 0.25:
                        raise RuntimeError(
                            "Deadline tolerance exceeded"
                        )

                    print(
                        "PASS: Deadline accuracy",
                        flush=True,
                    )

                print(
                    "PASS: Independent shutdown decision",
                    flush=True,
                )

                break

        else:
            raise RuntimeError("Integration test timed out")

        if executor.wait(timeout=2) != 0:
            raise RuntimeError("Executor exited unsuccessfully")

        latch_state = EmergencyLatch(latch_path).status()

        print(f"Latch state: {latch_state['state']}")

        if latch_state["state"] != "LATCHED":
            raise RuntimeError("Persistent latch not established")

        print("PASS: Persistent emergency latch")
        print("PASS: Integration simulation completed")

        return 0

    finally:
        parent.close()
        child.close()

        for process in processes:
            if process.poll() is None:
                process.kill()

            process.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
