# Thermal Guardian hardware-triggered shutdown acceptance test

Target: pots
Planned execution: After the 2026 holiday
Branch: feature/thermal-guardian

## Objective

Demonstrate the complete production emergency path using an actual
GPU temperature event.

The purpose is not to repeat isolated IPC, persistence, deadline,
executor, or override tests. Those have already received extensive
software acceptance testing.

The purpose is to verify their combined operation in the deployed
production system.

## Required event chain

1. Asteroids@home begins GPU computation.
2. GPU temperature crosses a temporary test threshold.
3. Production Thermal Guardian detects the emergency condition.
4. Monitor registers the emergency transition over authenticated IPC.
5. Independent deadline guardian accepts and persists the transition.
6. Shutdown challenge and bounded override behavior are exercised.
7. The independent guardian enforces the registered deadline.
8. The authorized poweroff service is dispatched.
9. The machine powers off.

## Preconditions

Before testing:

- Confirm that the production monitor and deadline guardian are healthy.
- Confirm that the shutdown authority marker and sudoers rule are valid.
- Verify that the guardian socket is available.
- Verify that both persistent state directories are healthy.
- Inspect the current production configuration and preserve an exact backup.
- Record baseline GPU edge, junction, memory, fan RPM, and power readings.
- Confirm that the GPU temperature responds predictably to Asteroids@home.
- Inspect the UPS software integration and confirm its current state.
- Confirm that the operator is physically present and can recover the machine.
- Save all work and stop unrelated workloads.
- Ensure that the machine can be safely powered back on.

## Temporary test configuration

Use a temporary test threshold derived from measured idle temperature
and observed Asteroids@home load behavior.

The threshold must be:

- Above the measured idle baseline.
- Below the expected test workload temperature.
- Consistent with a controlled test event.
- Restorable from the preserved production configuration.

Do not modify kernel thermal limits, firmware protections, GPU power
limits, or fan-control settings.

Do not use an arbitrary threshold without first observing the baseline.

## Execution

1. Capture the current configuration and its checksum.
2. Verify both systemd services before the test.
3. Apply the temporary test-only threshold.
4. Validate configuration syntax and sensor policy.
5. Start the GPU workload.
6. Observe the production monitor and guardian logs continuously.
7. Record the detected event and exact timestamps.
8. Confirm authenticated registration and guardian acknowledgement.
9. Observe the shutdown challenge.
10. Verify the bounded override behavior.
11. Allow the actual deadline to expire.
12. Verify privileged poweroff dispatch and physical shutdown.

The operator must not manually invoke the poweroff endpoint during
the acceptance test. The test must demonstrate the complete
event-driven production path.

## Abort conditions

Abort the test and restore the original configuration if:

- Sensor readings become unavailable or inconsistent.
- GPU temperatures approach actual hardware safety limits.
- Fan behavior is abnormal.
- IPC registration fails or cannot be confirmed.
- Guardian state and monitor state disagree.
- The countdown or override behaves unexpectedly.
- The UPS reports an unhealthy or unknown state.
- The machine becomes unstable.

Never bypass firmware or kernel thermal protection to complete
the test.

## Evidence to retain

- Original and temporary configuration checksums.
- Baseline and triggered sensor readings.
- Monitor journal.
- Deadline guardian journal.
- Poweroff service journal.
- Persistent deadline record.
- Exact event, registration, challenge, override, and dispatch timestamps.
- UPS status and event records.
- Final physical shutdown result.

## Recovery

After the machine is powered back on:

1. Confirm the original production configuration is restored.
2. Confirm the authority marker remains correctly configured.
3. Inspect the previous boot's systemd journals.
4. Inspect the deadline guardian's previous boot record.
5. Verify both services start normally.
6. Verify fresh IPC synchronization.
7. Verify the production monitor reports MONITORING.
8. Verify normal sensor readings and GPU fan telemetry.
9. Verify BOINC operation only after thermal monitoring is healthy.

## Acceptance criteria

PASS requires demonstration of the complete chain from a real
GPU temperature event through authenticated IPC, independent
deadline enforcement, operator challenge, and privileged poweroff.

A successful software simulation alone does not satisfy this test.

No production thermal thresholds are permanently changed as a
consequence of the test.
