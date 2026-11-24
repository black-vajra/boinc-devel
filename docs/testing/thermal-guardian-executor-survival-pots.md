# Independent emergency executor survival validation

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Systemd: 255.4
Branch: feature/thermal-guardian
Previous checkpoint: 17e3406

## Architecture

Three independent user-level systemd services:
- Emergency executor.
- Sensor-driven supervisor.
- Harmless dependent computation.

Each service occupied a separate control group.

Executor had no stop-propagating dependency
on the supervisor.

Supervisor watchdog: 5 seconds.
Emergency countdown: 7 seconds.

## Validation results

PASS: Real hardware sensor initialization.
PASS: Persistent ARMED state established.
PASS: Supervisor and executor service isolation.
PASS: Synthetic emergency deadline established.
PASS: Supervisor deliberately frozen using SIGSTOP.
PASS: Watchdog terminated frozen supervisor.
PASS: Dependent computation automatically stopped.
PASS: Independent executor survived supervisor death.
PASS: Harmless external action executed.
PASS: Original emergency deadline retained.
PASS: Persistent ARMED state retained.

## Timing

Authoritative monotonic deadline:
51685.867717086

External action timestamp:
51685.888624296

Deadline lateness:
20.907210 milliseconds.

Supervisor monotonic exit timestamp:
51683.931278

Executor action occurred approximately
1.957 seconds after supervisor exit.

Acceptance tolerance: 250 milliseconds.

## Existing regression suite

88 automated tests previously passed.

## Limitations

Synthetic emergency injection.
Harmless external marker-file action.
Dependent computation was a sleep process.
No real BOINC or VirtualBox termination tested.
No actual system poweroff.
No production privilege separation.
No executor crash recovery.
Desktop and diagnostics omitted from this fixture.
Test state was not reboot-persistent.

## Safety

No privileged operations.
No hardware settings changed.
No production services modified.
Actual shutdown authority remained disabled.
