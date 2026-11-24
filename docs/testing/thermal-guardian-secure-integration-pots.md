# Authenticated Thermal Guardian systemd integration

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Systemd: 255.4
Python: 3.12.3
Branch: feature/thermal-guardian
Previous checkpoint: f7558cd
Regression baseline: 144 passing tests

## Architecture

Independent authenticated executor service.
Independent sensor supervisor service.
Dependent simulated computation service.

Separate systemd control groups.
Computation BindsTo and After both protective services.
NotifyAccess=main retained.
Five-second watchdog for both protective services.
Automatic restart disabled.

Real hardware sensor sampling.
Isolated persistent recovery state.
Synthetic emergency and simulated external action.

## Supervisor failure during emergency

PASS: Authenticated emergency delivery.
PASS: Authoritative seven-second countdown.
PASS: Supervisor watchdog termination.
PASS: Dependent computation termination.
PASS: Independent executor survival.
PASS: External simulated action execution.
PASS: Persistent EMERGENCY state retained.

Authoritative deadline: 55403.325332051
External action: 55403.347444296
Deadline lateness: 22.112 milliseconds.
Acceptance limit: 250 milliseconds.

Computation stopped 2.377 milliseconds after
supervisor watchdog timeout.

## Startup interlock

PASS: Computation requested before protective readiness.
PASS: Computation MainPID remained zero.
PASS: Computation start job remained waiting.
PASS: Both protective services became ready.
PASS: Computation subsequently activated.

Supervisor-to-computation activation interval:
14.317 milliseconds.

## Executor failure during normal monitoring

PASS: Executor watchdog termination.
PASS: Dependent computation termination.
PASS: Supervisor detects connection reset.
PASS: Supervisor exits without continuing unprotected.

Watchdog detection: 4.298767 seconds.
Computation stop latency: 1.407 milliseconds.
Supervisor exit following executor exit:
165.530 milliseconds.

## Notification environment isolation

Initial session generated rejected subprocess
notification warnings.

NOTIFY_SOCKET removed from systemctl subprocess
environments.

PASS: Subsequent session showed no such warnings.
NotifyAccess=main retained.

## Host cleanup

PASS: No remaining loaded tg-test-* services.
PASS: Observation service remains active.
PASS: Production BOINC remains inactive.

## Evidence archives

~/thermal-guardian-validation/2026-11-24/secure-integration-survival/

~/thermal-guardian-validation/2026-11-24/secure-integration-executor-failure/

## Remaining limitations

Independent emergency protection following executor
failure during an active emergency remains unresolved.

Desktop operator connection must become optional.

Executor-to-supervisor per-message authentication
requires further integration.

Production supervisor requires structured handling
of communication failures.

Dummy computation stop timings do not establish
BOINC or VirtualBox workload termination timings.

Production BOINC interlock not yet deployed.

## Safety

No privileged execution.
No production installation modifications.
No hardware settings changed.
No genuine shutdown actions.
