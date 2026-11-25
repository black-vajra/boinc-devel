# Authenticated independent deadline integration

Date: 2026-11-24
Host: pots
Branch: feature/thermal-guardian

## Implementation

- Authenticated deadline registration and acknowledgement.
- Boot-scoped persistent emergency deadline.
- Independent deadline enforcement process.
- Synchronization of authorized operator override.
- Conservative handling of registration failures.

## Acceptance results

### Original countdown

PASS: Authenticated persistent registration.
PASS: Primary executor deliberately frozen.
PASS: Independent guardian executed.

Deadline lateness: 7.553 milliseconds.

### Authorized override

PASS: Authenticated persistent registration.
PASS: Authorized override synchronized.
PASS: Repeated override cannot renew.
PASS: Primary executor deliberately frozen.
PASS: Independent guardian executed.

Deadline lateness: 29.425 milliseconds.

Acceptance tolerance: 250 milliseconds.
Acceptance exit status: 0.

### Subsequent integrated acceptance

PASS: Authenticated persistent registration.
PASS: Executor deliberately frozen.
PASS: Independent guardian executed.
Deadline lateness: 6.786 ms.

PASS: Authorized override synchronized.
PASS: Repeated override cannot renew.
PASS: Executor deliberately frozen.
PASS: Independent guardian executed.
Deadline lateness: 24.932 ms.

### Executor-death acceptance

PASS: Authenticated deadline persisted.
PASS: Executor terminated by SIGKILL.
PASS: Independent guardian survived executor.
PASS: Guardian independently executed action.

Deadline lateness: 0.089 ms.

## Regression

154 tests passed in 54.663 seconds.
Exit status: 0.

Additional production integration:
- 9 production protocol and monitor/guardian tests passed.
- 16 existing production service and handoff tests passed.
- Combined focused regression: 25 passed.

## Evidence

Original:
~/thermal-guardian-validation/2026-11-24/authenticated-deadline/

Subsequent evidence directories are recorded in the corresponding
test execution output and production integration documentation.

## Limitations

- Earlier acceptance tests used separate processes rather than separate
  systemd service cgroups.
- Successful registration preceded injected executor failure.
- Storage stalls and registration failure races remain unvalidated.
- Immediate critical action was not independently tested against
  physical hardware shutdown.
- Duplicate external action coordination remains unvalidated.
- No physical shutdown timing guarantee.

The later production deployment separately establishes systemd
service separation on Pots.

## Safety

All acceptance emergency actions were simulated.
No privileged physical shutdown was performed during these tests.
No production BOINC changes were required.
No hardware changes were made.
