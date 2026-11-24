# Thermal Guardian persistent recovery interlock

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Systemd: 255.4
Branch: feature/thermal-guardian
Previous checkpoint: 6277c87

## Implementation

Independent persistent operating-state marker.

Production destination:
 /var/lib/thermal-guardian/operating-state.json

States:
- CLEAN
- ARMED
- EMERGENCY
- FAULT
- UNINITIALIZED

Only CLEAN permits initialization of a new
guardian operating session.

ARMED must be persisted before computation
is authorized.

Unexpected interruption leaves the previous
operating session ARMED and blocks recovery.

## Validation

PASS: Uninitialized state blocks startup.
PASS: Explicit recovery authorization.
PASS: Persistent arming.
PASS: Unauthorized arming rejected.
PASS: Interrupted session remains blocked.
PASS: Emergency state persistence.
PASS: Emergency prevents rearming.
PASS: Orderly shutdown transition.
PASS: Active computation prevents clean transition.
PASS: Unresolved emergency prevents clean transition.
PASS: Emergency cannot silently become CLEAN.
PASS: Corrupt record rejected.
PASS: Invalid state rejected.
PASS: Missing directory rejected.
PASS: Symbolic link rejected.
PASS: Named pipe rejected.
PASS: Private file permissions.
PASS: Recovery reason required.
PASS: Simulated persistence failure.

## Regression suite

Controller: 20 tests.
Executor: 7 tests.
Latch: 18 tests.
Action: 6 tests.
Shutdown backend: 12 tests.
Backend integration: 6 tests.
Recovery: 19 tests.

Total: 88 tests passed.
Runtime: 33.396 seconds.
Exit status: 0.

## Limitations

Production startup enforcement pending.
Trusted supervisor integration pending.
State transition serialization pending.
Live guardian readiness verification pending.
Actual computation-stop verification pending.
Physical power-loss durability not tested.
Directory synchronization failure recovery pending.

## Safety

All tests used temporary directories.
No privileged commands executed.
No production recovery state created.
No BOINC service modifications.
No actual system poweroff.
