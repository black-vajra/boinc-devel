# Thermal Guardian IPC transport resilience validation

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Systemd: 255.4
Python: 3.12.3
Branch: feature/thermal-guardian
Previous checkpoint: 60f3c9c

## Defects identified during source review

AuthorizationError inherits from PermissionError
and consequently OSError.

The executor previously caught OSError before
AuthorizationError, potentially interpreting an
authority violation as peer disconnection.

Zero-length SOCK_SEQPACKET messages were previously
indistinguishable from peer disconnection in the
application receiver.

## Corrections

Protocol and authorization exceptions handled
before general socket exceptions.

Linux SO_PASSCRED used to distinguish empty
messages from peer disconnection.

Ancillary data inspection and rejection added.
Unsolicited received file descriptors closed.
MSG_CMSG_CLOEXEC enabled.

## Validation

PASS: Thermal channel survives authority violation.
PASS: Operator channel survives authority violation.
PASS: Empty thermal packet preserves channel.
PASS: Empty packet during countdown preserves
subsequent critical escalation.

4 new regression tests passed.
124 previous regression tests passed.

Total: 128 tests.
Execution time: 42.336 seconds.
Exit status: 0.

## Limitations

Emergency-specific operator authorization pending.
Stale queued operator responses remain unresolved.
Cross-process authentication pending.
Dedicated ancillary-data regression tests pending.
Per-packet sender credentials not yet authenticated.
Executor readiness and health supervision pending.
Production IPC integration pending.

## Safety

No privileged execution.
No production installation modifications.
No BOINC service modifications.
No hardware settings changed.
All shutdown actions simulated.
