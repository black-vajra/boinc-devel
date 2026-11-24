# Thermal Guardian systemd supervision validation

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Systemd: 255.4
Branch: feature/thermal-guardian
Previous checkpoint: a89d35d

## Test architecture

Temporary user-level systemd services.

Guardian:
 Type=notify
 NotifyAccess=main
 WatchdogSec=5s
 WatchdogSignal=SIGKILL
 Restart=no

Dependent computation:
 BindsTo=tg-test-guardian.service
 After=tg-test-guardian.service

## Validation results

PASS: Readiness-gated computation startup.
Guardian initialization: 3.000 seconds.
Computation active 14.670 ms after READY.

PASS: Deliberately frozen guardian detected.
SIGSTOP to watchdog expiration: 4.648 seconds.

PASS: Automatic dependent computation termination.
Watchdog expiration to computation stopped: 2.002 ms.

PASS: Guardian failure classified as watchdog.

PASS: Orderly reverse shutdown ordering.
Computation stopped before guardian termination.

## Existing services

BOINC service reported inactive after testing.
Thermal observation service remained active.

## Existing automated regression suite

88 tests previously passed in 33.396 seconds.

## Limitations

Mock computation used an interruptible sleep process.
Actual BOINC and VirtualBox stop behavior not tested.
Mock heartbeat does not establish sensor health.
Independent executor survival requires separate supervision.
Persistent recovery state not yet connected.
Production privilege separation pending.

## Safety

User-level temporary test services only.
No actual shutdown authority.
No production service configuration modified.
No hardware settings modified.
