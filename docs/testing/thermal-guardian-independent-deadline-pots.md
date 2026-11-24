# Independent absolute emergency deadline validation

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Systemd: 255.4-1ubuntu8.19
Branch: feature/thermal-guardian
Previous checkpoint: 481859d

## Objective

Demonstrate independent absolute monotonic deadline
enforcement when a simulated primary executor becomes
unresponsive during the final 100 milliseconds of an
emergency countdown.

## Architecture

Separate systemd services and control groups.
Primary executor represented by watchdog fixture.
Independent guardian receives an absolute deadline.
No lifetime dependency between the two services.
Fault injection performed using a Linux PID file
descriptor.

All actions simulated.

## Results

Primary PID: 185706
Independent guardian PID: 185713

Original deadline:
57391.626273259

Guardian armed:
57384.654297638

Primary freeze confirmed:
57391.526695396

Remaining countdown at confirmed freeze:
99.578 milliseconds.

Simulated action timestamp:
57391.626375419

Deadline lateness:
0.102160 milliseconds.

Acceptance tolerance:
250 milliseconds.

PASS: Independent deadline registration.
PASS: Separate control groups.
PASS: Primary frozen within final 100 milliseconds.
PASS: Original deadline preserved.
PASS: Boot identity consistency.
PASS: Independent simulated action.
PASS: Deadline accuracy.
PASS: Primary watchdog termination.
PASS: No primary automatic restart.
PASS: Guardian successful completion.

## Interpretation

The independent guardian executed its simulated
action before primary watchdog expiration.

Deadline enforcement did not depend on detecting
primary executor failure.

## Limitations

Single timing experiment.
No real-time execution guarantee.

Primary executor was a watchdog simulation fixture,
not the authenticated secure executor.

Action timestamp records the beginning of simulated
action handling, not completion of physical shutdown.

Deadline supplied directly by the test harness.
Authenticated emergency registration not implemented.

Runtime evidence is not durable emergency persistence.
Operator override synchronization not implemented.
Duplicate action coordination not implemented.
Independent guardian failure recovery not implemented.

## Evidence archive

~/thermal-guardian-validation/2026-11-24/independent-deadline/

## Safety

No privileged execution.
No hardware modifications.
No production BOINC modifications.
No actual shutdown authority.
