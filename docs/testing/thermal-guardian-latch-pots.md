# Thermal Guardian persistent emergency latch

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Branch: feature/thermal-guardian

## Implementation

Persistent emergency record using atomic publication,
file synchronization and directory synchronization.

Production destination:
 /var/lib/thermal-guardian/emergency-latch.json

States:
- CLEAR
- LATCHED
- FAULT

LATCHED and FAULT prohibit unattended computation
once the production startup interlock is integrated.

The original emergency record is preserved.

## Validation

Complete regression suite:
- Controller: 20 tests.
- Executor: 7 tests.
- Latch: 18 tests.
- Total: 45 tests passed.
- Runtime: 28.258 seconds.
- Exit status: 0.

Validated persistence across independent processes,
malformed records, missing directories, permission
errors, broken symlinks and invalid emergency inputs.

## Safety

All latch tests used temporary directories.
No production latch created.
No actual shutdown commands executed.
No BOINC or hardware settings modified.

## Remaining limitations

- Abrupt physical power-loss persistence not tested.
- Concurrent emergency publication stress test pending.
- Administrative latch clearing not implemented.
- BOINC startup interlock not implemented.
- Independent persistence-worker integration pending.
- Interrupted emergency countdown recovery pending.
- Filesystem failure must not delay shutdown.
