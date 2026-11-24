#!/usr/bin/env python3

"""Independent absolute monotonic deadline experiment.

Simulation only. No hardware or shutdown authority.
"""

import json
import math
import os
import sys
import time

from pathlib import Path


def publish(directory, name, record):
    destination = directory / name
    temporary = directory / (name + ".tmp")

    temporary.write_text(json.dumps(record, indent=2))
    temporary.replace(destination)


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Development fixture cannot run as root")

    directory = Path(sys.argv[1])
    deadline = float(sys.argv[2])

    if not math.isfinite(deadline) or deadline <= 0:
        raise ValueError("Invalid monotonic deadline")

    os.umask(0o077)

    boot_id = Path(
        "/proc/sys/kernel/random/boot_id"
    ).read_text().strip()

    publish(directory, "armed.json", {
        "deadline": deadline,
        "armed_at": time.monotonic(),
        "boot_id": boot_id,
        "pid": os.getpid(),
        "cgroup": Path("/proc/self/cgroup").read_text().strip(),
    })

    print("PASS: Independent deadline armed", flush=True)

    while True:
        remaining = deadline - time.monotonic()

        if remaining <= 0:
            break

        time.sleep(remaining)

    action_at = time.monotonic()

    publish(directory, "action.json", {
        "deadline": deadline,
        "at": action_at,
        "lateness": action_at - deadline,
        "boot_id": boot_id,
        "pid": os.getpid(),
        "simulated": True,
    })

    print(
        f"PASS: Simulated action at {action_at:.9f}",
        flush=True,
    )

    print(
        f"Deadline lateness: {(action_at-deadline)*1000:.3f} ms",
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
