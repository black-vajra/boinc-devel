#!/usr/bin/env python3
"""Simulation-only independent deadline process. Linux monotonic clock."""
import argparse
import json
import selectors
import socket
import time


def run(sock, countdown=7, override=30, action=None):
    # Import inside child so the existing tested controller is canonical.
    from thermal_guardian_controller import EmergencyController, State
    controller = EmergencyController(countdown, override)
    sock.setblocking(False)
    selector = selectors.DefaultSelector()
    selector.register(sock, selectors.EVENT_READ)
    level = 'NORMAL'
    def emit(kind, **fields):
        # Telemetry must not block the timer. A full output queue can lose
        # simulated notifications; production action must not use this queue.
        try:
            sock.send(json.dumps(dict(kind=kind, at=time.monotonic(), **fields)).encode())
        except OSError:
            pass
    def execute_shutdown(decision):
        # Execute independently of notification delivery.
        if action is not None:
            action(decision)

        emit('SIMULATED_SHUTDOWN', reason=decision.reason)
        return 0

    emit('READY')
    while True:
        now = time.monotonic()
        decision = controller.update(now, level)
        if decision.shutdown_requested:
            return execute_shutdown(decision)
        timeout = None if decision.deadline is None else max(0, decision.deadline-now)
        events = selector.select(timeout)
        if not events:
            continue
        # One bounded datagram per iteration; recheck deadline before each.
        try:
            raw = sock.recv(4096)
        except BlockingIOError:
            continue
        if not raw:
            selector.unregister(sock)
            if controller.deadline is None:
                return 2
            # Peer loss must not cancel an active deadline.
            continue
        now = time.monotonic()
        decision = controller.update(now, level)
        if decision.shutdown_requested:
            return execute_shutdown(decision)
        try:
            msg = json.loads(raw)
            if not isinstance(msg, dict):
                continue
            kind = msg.get('kind')
            value = msg.get('value')
            if kind == 'THERMAL' and value in ('NORMAL','WARN','EMERGENCY','CRITICAL','FAULT'):
                level = value
                decision = controller.update(now, level)
            elif kind == 'OPERATOR' and value in ('YES','NO'):
                decision = controller.update(now, level, value)
            else:
                continue
        except (ValueError, TypeError, UnicodeError):
            continue
        if decision.shutdown_requested:
            return execute_shutdown(decision)
        emit('STATE', state=decision.state.value, deadline=decision.deadline)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fd', type=int, required=True)
    args = p.parse_args()
    with socket.socket(fileno=args.fd) as sock:
        return run(sock)


if __name__ == '__main__':
    raise SystemExit(main())
