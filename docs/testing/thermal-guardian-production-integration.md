# Thermal Guardian production deadline integration

Date: 2026-11-25
Target host: pots
Branch: feature/thermal-guardian

## Scope

Integrates the production monitor with a separately supervised systemd
deadline guardian. The guardian owns its boot-scoped persistent deadline
record and remains independently supervised if the monitor process exits.

The existing production monitor, controller, emergency latch, sensor
sampling, and narrowly authorized poweroff service remain in place.

## Components

- scripts/thermal_guardian_deadline_daemon.py:
  independent listener, persistent deadline owner, transition validator,
  and action dispatcher.
- scripts/thermal_guardian_deadline_client.py:
  monitor-side authenticated registration client with reconnect
  synchronization.
- scripts/thermal_guardian_deadline.py:
  boot-scoped persistent record, including immediate CRITICAL shutdown.
- scripts/thermal_guardian_ipc.py:
  Linux peer-credential and packet validation.
- scripts/thermal_guardian_service.py:
  production monitor registering emergency-state transitions.
- systemd/thermal-guardian-deadline.service:
  independently supervised deadline guardian.
- systemd/thermal-guardian.service:
  production hardware monitor, requiring and participating in the
  lifecycle of the independent guardian.
- systemd/thermal-guardian-poweroff.service:
  narrowly authorized privileged poweroff endpoint.

## Protocol and recovery

The guardian sends a synchronization record on connection. The monitor
registers COUNTDOWN, OVERRIDE, or SHUTDOWN transitions using a monotonically
increasing per-connection sequence.

The guardian persists a transition before acknowledging it.

Repeated state/deadline registration is idempotent. A stale monitor update
cannot roll back a guardian-side terminal SHUTDOWN decision.

The guardian continues enforcing a persisted deadline after monitor socket
loss. On guardian restart, it reloads the boot-scoped record and resumes
the same monotonic deadline.

A boot-ID mismatch or corrupt record fails closed.

The monitor's persistent service state remains authoritative for
sensor/controller recovery. The guardian's record is authoritative for
independent deadline enforcement.

## Shutdown authorization

Actual poweroff requires both the guardian's --enable-shutdown gate and
the root-owned authority marker:

/etc/thermal-guardian/ENABLE-SHUTDOWN

The privileged endpoint is:

thermal-guardian-poweroff.service

A narrowly scoped sudoers rule authorizes the thermal-guardian account
to start only that systemd service.

The installer does not independently create shutdown authority.

## Build and regression validation

PASS: Python compilation of production integration components.

PASS: 9 production protocol and monitor/guardian integration tests.

PASS: 16 production service and handoff tests.

PASS: Combined focused regression of 25 tests.

PASS: Shell syntax validation.

PASS: systemd-analyze verification of the monitor, guardian,
and poweroff units.

Earlier authenticated deadline acceptance also demonstrated
persistent registration, independent enforcement, bounded override,
and survival of deliberate executor termination.

## Pots production deployment — 2026-11-25

PASS: Independent deadline guardian installed and enabled.

PASS: Production monitor installed and enabled.

PASS: Both services observed active and running.

PASS: Monitor and guardian operate as separate systemd units
and service cgroups.

PASS: Monitor dependency on the deadline guardian established.

PASS: Guardian IPC registration socket present:

/run/thermal-guardian-deadline/registration.sock

PASS: Socket ownership and permissions verified.

PASS: Production monitor and independent guardian processes observed.

PASS: Shutdown authority marker created and verified:

/etc/thermal-guardian/ENABLE-SHUTDOWN

PASS: Marker is root-owned, read-only, and accessible to the
thermal-guardian group.

PASS: Narrowly scoped sudoers authorization installed and validated.

PASS: Guardian authorized to read shutdown marker.

PASS: Production monitor reports MONITORING.

PASS: Sensor inventory reports 29 sensors and zero faults
in the observed monitoring snapshot.

PASS: CPU, GPU, and NVMe thermal telemetry operational.

## Production observations

GPU fan telemetry was verified through the amdgpu hwmon interface.
Observed fan speed changed with operating conditions, including
approximately 625 RPM and subsequently 1044 RPM.

The motherboard IT87952 controller exposes PWM controls, but its
fan RPM inputs report zero. These readings require separate
hardware investigation and are not treated as proof of stopped fans.

Fan-control development is explicitly deferred to a separate workstream.

## Remaining acceptance work

The following end-to-end production sequence remains to be demonstrated:

1. Real hardware temperature crossing the configured emergency trigger.
2. Production monitor detecting the event.
3. Authenticated IPC registration and acknowledgement.
4. Independent guardian synchronization and deadline enforcement.
5. Operator shutdown challenge.
6. Actual privileged poweroff dispatch.

This test is scheduled for after the holiday.

The test will use a temporary, controlled GPU thermal threshold and
Asteroids@home workload to generate a reproducible trigger.

The ordinary production configuration must be backed up and restored
after the test.

The UPS software integration between Kubuntu and the UPS must also
be inspected before the physical shutdown acceptance test.

## Acceptance boundary

The production system is activated and monitoring.

The independent deadline mechanism and its authenticated integration
have substantial prior simulated acceptance evidence.

The complete hardware-triggered privileged shutdown sequence has not
yet received final physical acceptance.

No claim of successful physical shutdown testing is made here.
