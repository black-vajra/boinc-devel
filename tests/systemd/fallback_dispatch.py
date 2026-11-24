#!/usr/bin/env python3

"""Independent failure dispatch validation.

Simulation only. No shutdown authority.
"""

import json
import os
import sys
import time

from pathlib import Path


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Do not run this fixture as root")

    directory = Path(sys.argv[1])

    fields = (
        "MONITOR_SERVICE_RESULT",
        "MONITOR_EXIT_CODE",
        "MONITOR_EXIT_STATUS",
        "MONITOR_INVOCATION_ID",
        "MONITOR_UNIT",
        "INVOCATION_ID",
    )

    record = {
        "at": time.monotonic(),
        "pid": os.getpid(),
        "cgroup": Path("/proc/self/cgroup").read_text().strip(),
        "environment": {
            field: os.environ.get(field)
            for field in fields
        },
    }

    temporary = directory / "fallback-dispatch.tmp"
    destination = directory / "fallback-dispatch.json"

    temporary.write_text(json.dumps(record, indent=2))
    temporary.replace(destination)

    print(json.dumps(record, indent=2), flush=True)

    print("PASS: Independent fallback dispatched", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
