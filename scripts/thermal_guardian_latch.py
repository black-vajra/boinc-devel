#!/usr/bin/env python3

"""Persistent thermal emergency latch.

No shutdown commands, hardware writes or BOINC commands.

An existing or unreadable latch must prevent unattended
computation until an administrator investigates.
"""

import json
import math
import os
import socket
import tempfile
import uuid

from datetime import datetime, timezone
from pathlib import Path


DEFAULT_LATCH = Path(
    "/var/lib/thermal-guardian/emergency-latch.json"
)


class EmergencyLatch:

    def __init__(self, path=DEFAULT_LATCH):
        self.path = Path(path)

    def sync_directory(self):
        fd = os.open(
            self.path.parent,
            os.O_RDONLY | os.O_DIRECTORY
        )

        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def status(self):
        """Return CLEAR, LATCHED or FAULT."""

        if not self.path.parent.is_dir():
            return {
                "state": "FAULT",
                "reason": "Latch directory unavailable",
            }

        try:
            with self.path.open("r") as handle:
                record = json.load(handle)

        except FileNotFoundError:
            if os.path.lexists(self.path):
                return {
                    "state": "FAULT",
                    "reason": "Invalid latch path",
                }

            return {"state": "CLEAR"}

        except (OSError, ValueError, UnicodeError) as error:
            return {
                "state": "FAULT",
                "reason": str(error),
            }

        if not isinstance(record, dict):
            return {
                "state": "FAULT",
                "reason": "Invalid latch record",
            }

        required = {
            "version",
            "event_id",
            "hostname",
            "timestamp",
            "sensor",
            "temperature",
            "threshold",
            "level",
            "reason",
        }

        if (
            not required.issubset(record)
            or record["version"] != 1
            or record["level"] not in ("EMERGENCY", "CRITICAL")
        ):
            return {
                "state": "FAULT",
                "reason": "Malformed latch record",
            }

        return {
            "state": "LATCHED",
            "record": record,
        }

    def blocks_computation(self):
        return self.status()["state"] != "CLEAR"

    def create(
        self,
        sensor,
        temperature,
        threshold,
        level,
        reason,
    ):
        """Atomically preserve the first emergency event."""

        if level not in ("EMERGENCY", "CRITICAL"):
            raise ValueError("Invalid emergency level")

        if not all(
            math.isfinite(value)
            for value in (temperature, threshold)
        ):
            raise ValueError("Invalid temperature")

        current = self.status()

        if current["state"] != "CLEAR":
            return current

        record = {
            "version": 1,
            "event_id": str(uuid.uuid4()),
            "hostname": socket.gethostname(),
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "sensor": sensor,
            "temperature": temperature,
            "threshold": threshold,
            "level": level,
            "reason": reason,
        }

        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.path.parent,
                prefix=".emergency-latch-",
                delete=False,
            ) as handle:

                temp_path = Path(handle.name)

                os.fchmod(handle.fileno(), 0o600)

                json.dump(
                    record,
                    handle,
                    indent=2,
                    allow_nan=False,
                )

                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            # Publish atomically without overwriting an
            # existing emergency record.
            try:
                os.link(temp_path, self.path)
            except FileExistsError:
                pass

            self.sync_directory()

        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

        return self.status()
