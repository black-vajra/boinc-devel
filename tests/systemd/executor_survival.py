#!/usr/bin/env python3

"""Independent executor survival test.

Simulation only. No privileged operations or poweroff.
"""

import json
import socket
import subprocess
import sys
import time

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT / "scripts"))

from thermal_guardian_executor import run


def main():
    directory = Path(sys.argv[1])
    address = directory / "executor.sock"
    marker = directory / "action.json"

    def action(decision):
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json,sys,time;"
                    "from pathlib import Path;"
                    "Path(sys.argv[1]).write_text("
                    "json.dumps({"
                    "'executed':True,"
                    "'at':time.monotonic(),"
                    "'reason':sys.argv[2]"
                    "}))"
                ),
                str(marker),
                decision.reason,
            ],
            timeout=2,
            check=True,
        )

        print(
            "PASS: Independent external action executed",
            flush=True,
        )

    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
    ) as listener:

        listener.bind(str(address))
        listener.listen(1)
        listener.settimeout(30)

        print("Executor listening", flush=True)

        connection, _ = listener.accept()

        with connection:
            return run(connection, action=action)


if __name__ == "__main__":
    raise SystemExit(main())
