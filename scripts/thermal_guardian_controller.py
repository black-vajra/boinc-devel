#!/usr/bin/env python3

"""Thermal Guardian emergency decision controller.

Pure state machine. No hardware access, subprocesses,
filesystem writes or system shutdown commands.

The caller supplies monotonic time and thermal state.
"""

import math

from enum import Enum
from dataclasses import dataclass


class State(str, Enum):
    MONITORING = "MONITORING"
    COUNTDOWN = "COUNTDOWN"
    OVERRIDE = "OVERRIDE"
    SHUTDOWN = "SHUTDOWN"


@dataclass(frozen=True)
class Decision:
    state: State
    deadline: float | None
    reason: str
    shutdown_requested: bool


class EmergencyController:

    def __init__(self, countdown=7, override=30):

        if not math.isfinite(countdown) or countdown <= 0:
            raise ValueError("Invalid countdown")

        if not math.isfinite(override) or override <= 0:
            raise ValueError("Invalid override")

        self.countdown = countdown
        self.override = override

        self.state = State.MONITORING
        self.deadline = None
        self.reason = "Monitoring"
        self.last_time = None

    def decision(self):

        return Decision(
            state=self.state,
            deadline=self.deadline,
            reason=self.reason,
            shutdown_requested=self.state == State.SHUTDOWN,
        )

    def request_shutdown(self, reason):

        self.state = State.SHUTDOWN
        self.deadline = None
        self.reason = reason

        return self.decision()

    def update(self, now, thermal_level, operator=None):

        if not math.isfinite(now):
            raise ValueError("Invalid monotonic time")

        if self.last_time is not None and now < self.last_time:
            raise ValueError("Monotonic time moved backwards")

        self.last_time = now

        if thermal_level not in (
            "NORMAL",
            "WARN",
            "EMERGENCY",
            "CRITICAL",
            "FAULT",
        ):
            raise ValueError("Invalid thermal level")

        if operator not in (None, "YES", "NO"):
            raise ValueError("Invalid operator response")

        # Shutdown requests are irreversible within this
        # controller instance.
        if self.state == State.SHUTDOWN:
            return self.decision()

        # Absolute critical temperature overrides everything.
        if thermal_level == "CRITICAL":
            return self.request_shutdown(
                "Absolute critical temperature"
            )

        # Deadlines take precedence over operator responses.
        if self.deadline is not None and now >= self.deadline:

            if self.state == State.COUNTDOWN:
                return self.request_shutdown(
                    "Emergency countdown expired"
                )

            if self.state == State.OVERRIDE:
                return self.request_shutdown(
                    "Manual intervention period expired"
                )

        if self.state == State.MONITORING:

            if thermal_level == "EMERGENCY":
                self.state = State.COUNTDOWN
                self.deadline = now + self.countdown
                self.reason = "Thermal emergency detected"

            elif thermal_level == "FAULT":
                self.reason = "Required sensor fault"

            elif thermal_level == "WARN":
                self.reason = "Thermal warning"

            else:
                self.reason = "Monitoring"

            # An operator response cannot be accepted before
            # the corresponding emergency has been established.
            return self.decision()

        if self.state == State.COUNTDOWN:

            if operator == "YES":
                return self.request_shutdown(
                    "Operator requested immediate shutdown"
                )

            if operator == "NO":
                self.state = State.OVERRIDE
                self.deadline = now + self.override
                self.reason = "Manual intervention authorized"

            return self.decision()

        if self.state == State.OVERRIDE:

            if operator == "YES":
                return self.request_shutdown(
                    "Operator requested shutdown during override"
                )

            # Further NO responses cannot extend the deadline.
            return self.decision()

        return self.decision()
