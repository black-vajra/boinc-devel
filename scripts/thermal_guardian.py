#!/usr/bin/env python3

"""Thermal Guardian — Phase I observation engine.

Read-only hardware monitoring and diagnostic reporting.
This version contains no shutdown or hardware-control commands.
"""

import argparse
import fnmatch
import json
import math
import socket
import subprocess
import time

from collections import deque
from datetime import datetime
from pathlib import Path


HWMON_ROOT = Path("/sys/class/hwmon")
GPU_DEVICE = Path("/sys/bus/pci/devices/0000:03:00.0")

DEFAULT_CONFIG = (
    Path(__file__).resolve().parent.parent
    / "examples/thermal-guardian-pots.json"
)

DEFAULT_REPORT_DIR = (
    Path.home() / "Desktop/thermal-emergency"
)

LEVELS = {
    "NORMAL": 0,
    "WARN": 1,
    "EMERGENCY": 2,
    "CRITICAL": 3,
}


def timestamp():
    return datetime.now().astimezone().isoformat(
        timespec="seconds"
    )


def read_text(path):
    try:
        return path.read_text().strip()
    except OSError:
        return None


def read_number(path):
    value = read_text(path)

    if value is None:
        return None

    try:
        number = float(value)
    except ValueError:
        return None

    return number if math.isfinite(number) else None


def read_scaled(path, divisor):
    value = read_number(path)

    if value is None:
        return None

    return value / divisor


def discover_temperatures():
    readings = []

    for hwmon in sorted(HWMON_ROOT.glob("hwmon*")):
        driver = read_text(hwmon / "name")

        if not driver:
            continue

        device = str((hwmon / "device").resolve())

        for sensor in sorted(hwmon.glob("temp*_input")):
            prefix = sensor.name.removesuffix("_input")

            label = (
                read_text(hwmon / f"{prefix}_label")
                or prefix
            )

            temperature = read_scaled(sensor, 1000)

            readings.append({
                "driver": driver,
                "device": device,
                "label": label,
                "temperature": temperature,
                "kernel_max": read_scaled(
                    hwmon / f"{prefix}_max", 1000
                ),
                "kernel_critical": read_scaled(
                    hwmon / f"{prefix}_crit", 1000
                ),
                "kernel_emergency": read_scaled(
                    hwmon / f"{prefix}_emergency", 1000
                ),
                "source": str(sensor),
                "level": "OBSERVE",
            })

    return readings


def discover_gpu():
    result = {
        "busy_percent": read_number(
            GPU_DEVICE / "gpu_busy_percent"
        ),
        "memory_busy_percent": read_number(
            GPU_DEVICE / "mem_busy_percent"
        ),
    }

    for hwmon in GPU_DEVICE.glob("hwmon/hwmon*"):
        if read_text(hwmon / "name") != "amdgpu":
            continue

        attributes = {
            "power_watts": ("power1_average", 1000000),
            "power_cap_watts": ("power1_cap", 1000000),
            "fan_rpm": ("fan1_input", 1),
            "gpu_clock_mhz": ("freq1_input", 1000000),
            "memory_clock_mhz": ("freq2_input", 1000000),
        }

        for key, (filename, divisor) in attributes.items():
            result[key] = read_scaled(
                hwmon / filename, divisor
            )

    return result


def matches(reading, policy):
    return (
        reading["driver"] == policy["driver"]
        and policy["device"] in Path(
            reading["device"]
        ).parts
        and any(
            fnmatch.fnmatchcase(reading["label"], pattern)
            for pattern in policy["labels"]
        )
    )


def classify(temperature, policy):
    if temperature is None:
        return "UNREADABLE"

    if temperature <= -40 or temperature >= 200:
        return "INVALID"

    if temperature >= policy["critical"]:
        return "CRITICAL"

    if temperature >= policy["emergency"]:
        return "EMERGENCY"

    if temperature >= policy["warning"]:
        return "WARN"

    return "NORMAL"


def evaluate(readings, config):
    faults = []
    highest = "NORMAL"

    for policy in config["sensors"]:
        selected = [
            reading for reading in readings
            if matches(reading, policy)
        ]

        expected = policy["expected_count"]

        if len(selected) != expected:
            faults.append(
                f"{policy['name']}: expected {expected} "
                f"sensors, found {len(selected)}"
            )

        for reading in selected:
            reading["policy"] = policy["name"]
            reading["level"] = classify(
                reading["temperature"], policy
            )

            if reading["level"] in ("INVALID", "UNREADABLE"):
                faults.append(
                    f"{reading['driver']} "
                    f"{reading['label']}: "
                    f"{reading['level']}"
                )
                continue

            if LEVELS[reading["level"]] > LEVELS[highest]:
                highest = reading["level"]

    return highest, faults


def collect_command(command, timeout=2):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "command": command,
            "error": str(error),
        }


def write_report(report_dir, snapshot, history):
    report_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        "thermal-observation-"
        + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        + ".json"
    )

    path = report_dir / filename

    report = {
        "mode": "OBSERVATION_ONLY",
        "hostname": socket.gethostname(),
        "event": snapshot,
        "history": list(history),
        "diagnostics": [
            collect_command(["sensors"]),
            collect_command(["uptime"]),
            collect_command(["free", "-h"]),
            collect_command(["swapon", "--show"]),
            collect_command([
                "ps", "-eo",
                "pid,ppid,psr,pcpu,pmem,comm",
                "--sort=-pcpu"
            ]),
            collect_command([
                "systemctl", "status",
                "boinc-client.service", "--no-pager"
            ]),
            collect_command([
                "journalctl", "-k", "-n", "80",
                "--no-pager"
            ]),
        ],
    }

    path.write_text(
        json.dumps(report, indent=2) + "\n"
    )

    print(f"REPORT: {path}", flush=True)


def display(snapshot):
    print(
        f"\n{snapshot['timestamp']} | "
        f"THERMAL STATE: {snapshot['level']}",
        flush=True,
    )

    for reading in snapshot["temperatures"]:
        if reading["level"] == "OBSERVE":
            continue

        temperature = reading["temperature"]

        value = (
            f"{temperature:.1f} C"
            if temperature is not None
            else "UNAVAILABLE"
        )

        print(
            f"  {reading['policy']:24} "
            f"{reading['label']:14} "
            f"{value:14} {reading['level']}"
        )

    for fault in snapshot["faults"]:
        print(f"  SENSOR FAULT: {fault}")

    gpu = snapshot["gpu"]

    print(
        f"  GPU utilization: {gpu.get('busy_percent')}% | "
        f"Power: {gpu.get('power_watts')} W | "
        f"Cap: {gpu.get('power_cap_watts')} W | "
        f"Fan: {gpu.get('fan_rpm')} RPM",
        flush=True,
    )


def validate_config(config):
    if config["hostname"] != socket.gethostname():
        raise ValueError(
            "Configuration does not match this host"
        )

    for field in (
        "poll_interval",
        "history_seconds",
        "status_interval",
    ):
        value = config[field]

        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"Invalid {field}")

    for policy in config["sensors"]:
        if not (
            policy["warning"]
            < policy["emergency"]
            < policy["critical"]
        ):
            raise ValueError(
                f"Invalid thresholds: {policy['name']}"
            )

        if policy["expected_count"] < 1:
            raise ValueError(
                f"Invalid sensor count: {policy['name']}"
            )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG
    )

    parser.add_argument(
        "--report-dir", type=Path, default=DEFAULT_REPORT_DIR
    )

    parser.add_argument(
        "--once", action="store_true"
    )

    parser.add_argument(
        "--simulate-junction", type=float, default=None
    )

    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    validate_config(config)

    history = deque()

    last_display = float("-inf")
    last_state = None

    print("========================================")
    print(" THERMAL GUARDIAN — OBSERVATION ONLY")
    print(" Shutdown authority: DISABLED")
    print(" Hardware modification: DISABLED")
    print(f" Host: {socket.gethostname()}")
    print(f" Poll interval: {config['poll_interval']}s")
    print(f" History: {config['history_seconds']}s")
    print("========================================")

    while True:
        now = time.monotonic()

        readings = discover_temperatures()

        if args.simulate_junction is not None:
            for reading in readings:
                if (
                    reading["driver"] == "amdgpu"
                    and reading["label"] == "junction"
                    and "0000:03:00.0" in Path(
                        reading["device"]
                    ).parts
                ):
                    reading["temperature"] = (
                        args.simulate_junction
                    )
                    reading["simulated"] = True

        level, faults = evaluate(readings, config)

        snapshot = {
            "timestamp": timestamp(),
            "simulated": args.simulate_junction is not None,
            "level": level,
            "faults": faults,
            "temperatures": readings,
            "gpu": discover_gpu(),
        }

        history.append((now, snapshot))

        while (
            history
            and now - history[0][0]
            > config["history_seconds"]
        ):
            history.popleft()

        state = (level, tuple(faults))

        if (
            state != last_state
            or now - last_display >= config["status_interval"]
        ):
            display(snapshot)
            last_display = now

        if state != last_state and (
            level in ("EMERGENCY", "CRITICAL") or faults
        ):
            print(
                "OBSERVATION: Emergency or sensor fault detected."
            )
            print("OBSERVATION: No shutdown will occur.")

            try:
                write_report(
                    args.report_dir,
                    snapshot,
                    [item[1] for item in history],
                )
            except OSError as error:
                print(f"REPORT FAILURE: {error}", flush=True)

        last_state = state

        if args.once:
            return 2 if faults else 0

        elapsed = time.monotonic() - now

        time.sleep(max(
            0, config["poll_interval"] - elapsed
        ))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nThermal Guardian observation stopped.")
