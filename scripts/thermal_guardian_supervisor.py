#!/usr/bin/env python3

"""Thermal Guardian sensor-driven supervisor.

Development mode only.
No poweroff authority or hardware modifications.
"""

import argparse
import json
import os
import socket
import time

from pathlib import Path

from thermal_guardian import (
    discover_temperatures,
    discover_gpu,
    evaluate,
    validate_config,
    timestamp,
)

from thermal_guardian_recovery import RecoveryState
from thermal_guardian_latch import EmergencyLatch


def notify(message):
    address = os.environ["NOTIFY_SOCKET"]

    if address.startswith("@"):
        address = "\0" + address[1:]

    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_DGRAM,
    ) as sock:

        sock.settimeout(0.5)
        sock.connect(address)
        sock.sendall(message.encode())


def sample(config):
    readings = discover_temperatures()

    level, faults = evaluate(readings, config)

    return {
        "timestamp": timestamp(),
        "level": level,
        "faults": faults,
        "temperatures": readings,
        "gpu": discover_gpu(),
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config", type=Path, required=True
    )

    parser.add_argument(
        "--state-dir", type=Path, required=True
    )

    args = parser.parse_args()

    # This development supervisor must not run as root.
    if os.geteuid() == 0:
        raise RuntimeError(
            "Development supervisor cannot run as root"
        )

    config = json.loads(args.config.read_text())
    validate_config(config)

    recovery = RecoveryState(
        args.state_dir / "operating-state.json"
    )

    latch = EmergencyLatch(
        args.state_dir / "emergency-latch.json"
    )

    print("=== THERMAL GUARDIAN SUPERVISOR ===", flush=True)
    print("Shutdown authority: DISABLED", flush=True)

    state = recovery.status()

    print(f"Persistent state: {state}", flush=True)

    if state != "CLEAN":
        print("FAIL: Recovery authorization required", flush=True)
        return 2

    if latch.blocks_computation():
        print("FAIL: Emergency latch blocks startup", flush=True)
        return 2

    snapshot = sample(config)

    if snapshot["faults"]:
        print(
            f"FAIL: Required sensor faults: {snapshot['faults']}",
            flush=True,
        )
        return 2

    if snapshot["level"] != "NORMAL":
        print(
            f"FAIL: Unsafe startup state: {snapshot['level']}",
            flush=True,
        )
        return 2

    print("PASS: Required sensors validated", flush=True)

    recovery.arm()

    print("PASS: Persistent ARMED state established", flush=True)

    notify(
        "READY=1\n"
        "STATUS=Sensor validation complete; guardian armed"
    )

    print("PASS: Guardian READY", flush=True)

    next_status = 0

    while True:
        started = time.monotonic()

        snapshot = sample(config)

        level = snapshot["level"]
        faults = snapshot["faults"]

        if level in ("EMERGENCY", "CRITICAL"):
            print(
                "FAIL: Thermal emergency detected",
                flush=True,
            )

            recovery.emergency(
                f"Thermal state: {level}"
            )

            return 3

        if faults:
            print(
                f"FAIL: Required sensor faults: {faults}",
                flush=True,
            )

            # Retain ARMED state to block unattended recovery.
            return 4

        if latch.blocks_computation():
            print(
                "FAIL: Emergency latch no longer clear",
                flush=True,
            )
            return 5

        if recovery.status() != "ARMED":
            print(
                "FAIL: Operating state unexpectedly changed",
                flush=True,
            )
            return 6

        # Heartbeat only follows successful sensor sampling
        # and persistent-state verification.
        notify(
            f"WATCHDOG=1\nSTATUS=Thermal state: {level}"
        )

        if started >= next_status:
            print(
                f"{snapshot['timestamp']} | "
                f"State: {level} | "
                f"Sensors: {len(snapshot['temperatures'])} | "
                f"Faults: {len(faults)}",
                flush=True,
            )

            next_status = started + 10

        elapsed = time.monotonic() - started

        time.sleep(max(
            0, config["poll_interval"] - elapsed
        ))


if __name__ == "__main__":
    raise SystemExit(main())
