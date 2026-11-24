#!/usr/bin/env python3

"""Persistent Thermal Guardian operating state.

No shutdown commands or hardware access.
State transitions require a trusted, serialized caller.
"""

import json
import os
import stat
import tempfile

from datetime import datetime, timezone
from pathlib import Path


DEFAULT_STATE = Path(
    "/var/lib/thermal-guardian/operating-state.json"
)


class RecoveryState:

    def __init__(self, path=DEFAULT_STATE):
        self.path = Path(path)

    def status(self):
        try:
            if not self.path.parent.is_dir():
                return "FAULT"

            fd = os.open(
                self.path,
                os.O_RDONLY
                | os.O_NOFOLLOW
                | os.O_NONBLOCK,
            )

            with os.fdopen(fd, "r") as handle:
                info = os.fstat(handle.fileno())

                if not stat.S_ISREG(info.st_mode):
                    return "FAULT"

                if info.st_size > 65536:
                    return "FAULT"

                record = json.load(handle)

        except FileNotFoundError:
            return "UNINITIALIZED"

        except (OSError, ValueError, UnicodeError):
            return "FAULT"

        if not isinstance(record, dict):
            return "FAULT"

        if record.get("version") != 1:
            return "FAULT"

        state = record.get("state")

        if state not in ("CLEAN", "ARMED", "EMERGENCY"):
            return "FAULT"

        return state

    def _write(self, state, reason):
        record = {
            "version": 1,
            "state": state,
            "reason": reason,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.path.parent,
                prefix=".operating-state-",
                delete=False,
            ) as handle:

                temp_path = Path(handle.name)

                os.fchmod(handle.fileno(), 0o600)

                json.dump(record, handle)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temp_path, self.path)

            fd = os.open(
                self.path.parent,
                os.O_RDONLY | os.O_DIRECTORY,
            )

            try:
                os.fsync(fd)
            finally:
                os.close(fd)

        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

        if self.status() != state:
            raise RuntimeError(
                "Persistent state verification failed"
            )

        return state

    def authorize_recovery(self, reason):
        """Called only after explicit administrator approval."""

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Recovery reason required")

        return self._write("CLEAN", reason)

    def arm(self):
        if self.status() != "CLEAN":
            raise RuntimeError(
                "Recovery authorization required"
            )

        return self._write(
            "ARMED",
            "Guardian operating session armed",
        )

    def emergency(self, reason):
        return self._write("EMERGENCY", reason)

    def clean_shutdown(
        self,
        computation_stopped=False,
        emergency_clear=False,
    ):
        if computation_stopped is not True:
            raise RuntimeError("Computation not stopped")

        if emergency_clear is not True:
            raise RuntimeError("Emergency not cleared")

        if self.status() != "ARMED":
            raise RuntimeError(
                "Unsafe operating-state transition"
            )

        return self._write(
            "CLEAN",
            "Verified orderly shutdown",
        )

    def permits_new_session(self):
        return self.status() == "CLEAN"
