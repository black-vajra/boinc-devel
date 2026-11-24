# Thermal Guardian independent termination dispatch

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Systemd: 255.4-1ubuntu8.19
Branch: feature/thermal-guardian
Previous checkpoint: 16386ce

## Independent watchdog failure dispatch

PASS: OnFailure activates independent handler.
PASS: Handler executes in separate control group.
PASS: Originating unit metadata.
PASS: Originating invocation metadata.
PASS: Watchdog failure classification.
PASS: Handler exit status zero.
PASS: No fallback during normal monitoring.

Initial freeze-to-handler interval:
4.815508 seconds.

Initial watchdog timeout to handler evidence:
32.111 milliseconds.

## OnFailure coverage limitation

PASS: Administrative stop does not trigger OnFailure.
OBSERVED: Unexpected SIGTERM also does not trigger
OnFailure when classified as successful termination.

Therefore OnFailure alone is insufficient.

## Shared-handler metadata ambiguity

Configuring OnFailure and OnSuccess to reference
the same handler caused ambiguous trigger source
warnings.

All MONITOR_* variables were absent.

Dispatch succeeded but metadata validation failed.

## Separate termination handlers

Separate OnSuccess and OnFailure units execute
the same underlying Python implementation.

PASS: Successful termination dispatch.
PASS: Watchdog failure dispatch.
PASS: Originating invocation verification.
PASS: Originating unit verification.
PASS: Complete termination metadata.
PASS: Separate evidence records.

No ambiguous trigger warnings in corrected tests.

SIGTERM to handler evidence logged:
31.132 milliseconds.

Watchdog timeout to handler evidence logged:
29.182 milliseconds.

Complete watchdog dispatch interval:
5.136510 seconds.

## Administrative termination

PASS: Administrative stop dispatches success handler.
PASS: Originating invocation verified.

Unexpected SIGTERM and administrative stop produced
identical termination classifications:

MONITOR_SERVICE_RESULT=success
MONITOR_EXIT_CODE=killed
MONITOR_EXIT_STATUS=TERM

Administrative authorization cannot be inferred
from termination metadata.

Administrative stop completion to handler evidence:
26.643 milliseconds.

## Architectural conclusions

Use separate termination dispatch units for each
trigger type and monitored protective service.

Explicit orderly-stop authorization is required.

An emergency must not be cancelled by administrative
termination authorization.

Five-second watchdog detection cannot guarantee
preservation of an existing seven-second emergency
deadline.

Independent deadline enforcement remains necessary.

## Evidence archive

~/thermal-guardian-validation/2026-11-24/fallback-dispatch/

## Limitations

User-manager runtime validation only.
No production system-manager validation.
No emergency decision policy implemented.
No independent deadline mechanism implemented.
No persistent state serialization implemented.
No simultaneous failure coordination implemented.

Measured dispatch intervals are observations,
not guaranteed real-time bounds.

## Safety

No privileged execution.
No production service modifications.
No hardware settings changed.
No actual shutdown authority.
All fallback actions simulated.
