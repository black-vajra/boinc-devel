# Thermal Guardian authoritative desktop synchronization

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Branch: feature/thermal-guardian

## Implementation

Both emergency desktop windows use the independent
executor's absolute monotonic deadline.

Initial emergency countdown: 7 seconds.
Manual intervention period: 30 seconds.
Additional manual override is not offered.
Alarm is not repeated during manual intervention.

## Standalone validation

PASS: Artificial two-second GUI launch delay.
UI exit status: 30.
Deadline lateness: 44.635 ms.

PASS: Manual intervention window timeout.
UI exit status: 30.

PASS: Already-expired deadline.
UI exit status: 30.

## Integrated validation

PASS: Unattended emergency.
Deadline lateness: 7.213 ms.

PASS: Manual intervention expiration.
Deadline lateness: 1.533 ms.

PASS: Repeated unattended emergency.
Deadline lateness: 6.916 ms.

PASS: Immediate shutdown request during override.
Request occurred 18.165952 seconds before deadline.

PASS: Persistent emergency latch in every scenario.

## Safety and limitations

Simulation only.
No actual system shutdown.
No production latch.
No hardware settings modified.

Visual inspection and keyboard/window dismissal
resistance require explicit operator confirmation.

Independent diagnostic collection, actual shutdown
authority, executor crash recovery and production
startup interlocks remain pending.
