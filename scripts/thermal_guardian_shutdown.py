#!/usr/bin/env python3

"""Thermal Guardian shutdown action backend.

Development implementation.
Default commands are harmless.
No privileged command-line interface.
"""

import math
import subprocess
import time

from dataclasses import dataclass


@dataclass(frozen=True)
class Attempt:
    stage: str
    status: str
    returncode: int | None
    elapsed: float
    error: str | None = None


@dataclass(frozen=True)
class ShutdownResult:
    accepted: bool
    attempts: tuple


class ShutdownBackend:

    def __init__(
        self,
        primary=("/usr/bin/true",),
        fallback=("/usr/bin/true",),
        primary_timeout=2.0,
        fallback_timeout=2.0,
    ):
        for value in (primary_timeout, fallback_timeout):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Invalid command timeout")

        self.primary = tuple(primary)
        self.fallback = tuple(fallback)

        if not self.primary or not self.fallback:
            raise ValueError("Empty shutdown command")

        self.primary_timeout = primary_timeout
        self.fallback_timeout = fallback_timeout

    def attempt(self, stage, command, timeout):
        started = time.monotonic()

        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
                shell=False,
            )

            return Attempt(
                stage=stage,
                status=(
                    "ACCEPTED"
                    if result.returncode == 0
                    else "FAILED"
                ),
                returncode=result.returncode,
                elapsed=time.monotonic() - started,
            )

        except subprocess.TimeoutExpired:
            return Attempt(
                stage=stage,
                status="TIMEOUT",
                returncode=None,
                elapsed=time.monotonic() - started,
                error="Command timeout expired",
            )

        except OSError as error:
            return Attempt(
                stage=stage,
                status="ERROR",
                returncode=None,
                elapsed=time.monotonic() - started,
                error=str(error),
            )

    def execute(self):
        primary = self.attempt(
            "PRIMARY",
            self.primary,
            self.primary_timeout,
        )

        if primary.status == "ACCEPTED":
            return ShutdownResult(True, (primary,))

        fallback = self.attempt(
            "FALLBACK",
            self.fallback,
            self.fallback_timeout,
        )

        return ShutdownResult(
            fallback.status == "ACCEPTED",
            (primary, fallback),
        )

    def __call__(self, decision):
        return self.execute()
