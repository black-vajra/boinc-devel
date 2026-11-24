# Thermal Guardian cross-process IPC validation

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Systemd: 255.4
Python: 3.12.3
Branch: feature/thermal-guardian
Previous checkpoint: d6d5009

## Kernel credential experiment

Parent PID: 182330
Child PID: 182331
UID: 1000
GID: 1000

SO_PEERCRED retained the original connection
identity of PID 182330.

SCM_CREDENTIALS identified the actual message
sender as PID 182331.

PASS: Inherited descriptor distinguished from
the original authorized process.

## Implementation

Connection-level SO_PEERCRED authorization.
Per-message SCM_CREDENTIALS authorization.
SO_PASSCRED enabled before message transmission.
Exact PID, UID and GID matching.
Malformed credential rejection.
Missing credential rejection.
Credential mismatch rejection.
Existing emergency token enforcement retained.

## Validation

PASS: Inherited thermal descriptor rejected.
PASS: Inherited operator descriptor rejected.
PASS: Legitimate sender survives impersonation.
PASS: Real cross-process connection authenticated.
PASS: Unauthorized PID rejected.
PASS: Unsolicited descriptor rejected.
PASS: No descriptor leakage in tested case.

5 new regression tests passed.
133 previous regression tests passed.

Total: 138 tests.
Execution time: 50.417 seconds.
Exit status: 0.

## Limitations

PID reuse remains a consideration.
Privileged credential impersonation not addressed.
Production socket ownership not yet validated.
Separate privileged services not yet integrated.
Private desktop descriptor delivery pending.
Executor readiness and health supervision pending.
Emergency persistence across executor failure pending.

Descriptor leakage validation covers the tested
ancillary-data case, not every possible malformed
ancillary-data combination.

## Safety

No privileged execution.
No production installation modifications.
No BOINC service modifications.
No hardware settings changed.
All shutdown actions simulated.
