#!/usr/bin/env python3

"""Actual systemd notification compatibility test.

Simulation only. No hardware or shutdown authority.
"""

import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT / "scripts"))

from thermal_guardian_secure_executor import run


def simulated_action(decision):
    print(
        f"SIMULATED ACTION: {decision.reason}",
        flush=True,
    )


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Do not run this fixture as root")

    thermal_rx, thermal_tx = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
    )

    operator_rx, operator_tx = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
    )

    with thermal_rx, thermal_tx, operator_rx, operator_tx:
        print(
            "Authenticated executor notification test",
            flush=True,
        )

        return run(
            thermal_rx,
            operator_rx,
            thermal_uid=os.getuid(),
            operator_uid=os.getuid(),
            thermal_pid=os.getpid(),
            operator_pid=os.getpid(),
            action=simulated_action,
            notify_address=os.environ["NOTIFY_SOCKET"],
        )


if __name__ == "__main__":
    raise SystemExit(main())
