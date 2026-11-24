# Thermal Guardian IPC authentication validation

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Systemd: 255.4
Python: 3.12.3
Branch: feature/thermal-guardian
Previous checkpoint: daab19f

## Implementation

Linux SO_PEERCRED credential retrieval.
Explicit UID and optional PID authorization.
Separate thermal and operator message authorities.
Strict JSON message schema.
Duplicate-field rejection.
UTF-8 validation.
4096-byte maximum packet size.
Socket packet truncation detection.
Peer disconnection detection.

## Validation

PASS: All 23 new IPC tests.
PASS: All 88 existing regression tests.

Total: 111 tests.
Execution time: 33.410 seconds.
Exit status: 0.

## Authority separation

Thermal channel:
 NORMAL
 WARN
 EMERGENCY
 CRITICAL
 FAULT

Operator channel:
 YES
 NO

Neither channel may exercise the authority
assigned to the other.

## Limitations

IPC validation module not yet integrated
into the running emergency executor.

Credential tests use same-process socket pairs.
Cross-process authentication remains untested.
Production socket ownership remains untested.
PID reuse and descriptor inheritance require
additional consideration.
Operator responses not yet bound to an
individual emergency session.
Connection exhaustion and message flooding
remain untested.

## Safety

No privileged execution.
No production installation modifications.
No BOINC service modifications.
No hardware settings changed.
Actual shutdown authority remains disabled.
