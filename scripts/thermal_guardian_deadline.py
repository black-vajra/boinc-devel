#!/usr/bin/env python3

"""Boot-scoped persistent emergency deadline.

No shutdown authority or hardware modifications.
Transitions require a single trusted writer.
"""

import json
import math
import os
import stat
import tempfile
import time
import uuid

from pathlib import Path


class DeadlineRecord:

    def __init__(self, path):
        self.path = Path(path)
        self.boot_id = Path(
            "/proc/sys/kernel/random/boot_id"
        ).read_text().strip()

    def validate(self, record):
        required = {
            "version",
            "boot_id",
            "event_id",
            "state",
            "initial_deadline",
            "deadline",
            "override_used",
        }

        if not isinstance(record, dict):
            raise ValueError("Invalid deadline record")

        if set(record) != required:
            raise ValueError("Invalid deadline fields")

        if type(record["version"]) is not int:
            raise ValueError("Invalid version")

        if record["version"] != 1:
            raise ValueError("Unsupported deadline version")

        if record["boot_id"] != self.boot_id:
            raise RuntimeError("Emergency belongs to another boot")

        uuid.UUID(record["event_id"])

        if record["state"] not in (
            "COUNTDOWN", "OVERRIDE", "SHUTDOWN"
        ):
            raise ValueError("Invalid emergency state")

        for key in ("initial_deadline", "deadline"):
            value = record[key]

            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError("Invalid monotonic deadline")

        if type(record["override_used"]) is not bool:
            raise ValueError("Invalid override flag")

        if record["state"] == "COUNTDOWN":
            if record["override_used"]:
                raise ValueError("Unexpected override")

            if record["deadline"] != record["initial_deadline"]:
                raise ValueError("Initial deadline changed")

        if record["state"] == "OVERRIDE":
            if not record["override_used"]:
                raise ValueError("Missing override authorization")

        return record

    def load(self):
        fd = os.open(
            self.path,
            os.O_RDONLY |
            os.O_NOFOLLOW |
            os.O_NONBLOCK,
        )

        with os.fdopen(fd, "r") as handle:
            info = os.fstat(handle.fileno())

            if not stat.S_ISREG(info.st_mode):
                raise RuntimeError("Unsafe deadline file")

            if info.st_size > 65536:
                raise RuntimeError("Oversized deadline record")

            record = json.load(handle)

        return self.validate(record)

    def _write(self, record, initial=False):
        self.validate(record)

        temporary = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.path.parent,
                prefix=".deadline-",
                delete=False,
            ) as handle:

                temporary = Path(handle.name)

                os.fchmod(handle.fileno(), 0o600)

                json.dump(
                    record,
                    handle,
                    allow_nan=False,
                    indent=2,
                )

                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            if initial:
                os.link(temporary, self.path)
            else:
                os.replace(temporary, self.path)

            fd = os.open(
                self.path.parent,
                os.O_RDONLY | os.O_DIRECTORY,
            )

            try:
                os.fsync(fd)
            finally:
                os.close(fd)

        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

        if self.load() != record:
            raise RuntimeError("Deadline verification failed")

        return record

    def register(self, deadline):
        record = {
            "version": 1,
            "boot_id": self.boot_id,
            "event_id": str(uuid.uuid4()),
            "state": "COUNTDOWN",
            "initial_deadline": deadline,
            "deadline": deadline,
            "override_used": False,
        }

        return self._write(record, initial=True)

    def override(self, event_id, deadline):
        record = self.load()
        now = time.monotonic()

        if record["event_id"] != event_id:
            raise RuntimeError("Emergency identity mismatch")

        if record["state"] != "COUNTDOWN":
            raise RuntimeError("Override unavailable")

        if record["override_used"]:
            raise RuntimeError("Override already used")

        if now >= record["deadline"]:
            raise RuntimeError("Original deadline expired")

        if (
            type(deadline) not in (int, float)
            or not math.isfinite(deadline)
            or deadline <= now
            or deadline > now + 30
        ):
            raise ValueError("Invalid override deadline")

        record["deadline"] = deadline
        record["override_used"] = True
        record["state"] = "OVERRIDE"

        return self._write(record)

    def request_shutdown(self, event_id):
        record = self.load()

        if record["event_id"] != event_id:
            raise RuntimeError("Emergency identity mismatch")

        if record["state"] == "SHUTDOWN":
            return record

        record["state"] = "SHUTDOWN"
        record["deadline"] = min(
            record["deadline"],
            time.monotonic(),
        )

        return self._write(record)

    def due(self):
        record = self.load()

        return (
            record["state"] == "SHUTDOWN"
            or time.monotonic() >= record["deadline"]
        )
