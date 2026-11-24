#!/usr/bin/env python3

"""Restricted Thermal Guardian launcher.

This development version permits observation only.
No shutdown authority.
"""

import os
import runpy
import sys

from pathlib import Path


INSTALL_DIR = Path("/usr/local/lib/thermal-guardian")

ALLOWED_MODULES = {
    "observation": "thermal_guardian",
}


def main():
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError(
            "Launcher requires Python -I -S"
        )

    if len(sys.argv) < 2:
        raise SystemExit("Entry point required")

    entry = sys.argv[1]

    if entry not in ALLOWED_MODULES:
        raise SystemExit("Unauthorized entry point")

    # No synthetic emergency injection through the
    # privileged observation launcher.
    if any(
        arg.startswith("--simulate")
        for arg in sys.argv[2:]
    ):
        raise SystemExit("Simulation argument prohibited")

    # Restrict privileged observation to a fixed
    # configuration and report destination.
    if sys.argv[2:]:
        raise SystemExit("Additional arguments prohibited")

    info = INSTALL_DIR.stat()

    if info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError("Unsafe installation directory")

    sys.path.insert(0, str(INSTALL_DIR))

    sys.argv = [
        ALLOWED_MODULES[entry],
        "--config",
        "/etc/thermal-guardian/pots.json",
        "--report-dir",
        "/var/log/thermal-guardian",
        "--once",
    ]

    runpy.run_module(
        ALLOWED_MODULES[entry],
        run_name="__main__",
    )


if __name__ == "__main__":
    main()
