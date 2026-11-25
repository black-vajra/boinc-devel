# Thermal Guardian production activation — Pots

Date: 2026-11-25
Host: pots
Branch: feature/thermal-guardian

## Objective

Record activation of the production Thermal Guardian monitor and
independent emergency deadline guardian.

## Deployment

The following services are installed and enabled:

- thermal-guardian.service
- thermal-guardian-deadline.service

The production monitor depends on the independent deadline guardian.
The services run in separate systemd units and cgroups.

## Shutdown authorization

The following authority marker was created:

/etc/thermal-guardian/ENABLE-SHUTDOWN

Verified properties:

- Root ownership.
- Read-only permissions for owner and group.
- thermal-guardian group ownership.
- Guardian read access.

A narrowly scoped sudoers rule authorizes:

thermal-guardian ALL=(root) NOPASSWD: /usr/bin/systemctl start thermal-guardian-poweroff.service

Validation:

PASS: visudo parsed all sudoers files.
PASS: Guardian authorization verified.
PASS: Authority marker verified.
PASS: Guardian can read authority marker.

## Runtime observations

At approximately 17:31 EST:

- Independent deadline guardian restarted successfully.
- Production monitor restarted through its systemd dependency lifecycle.
- Both services subsequently entered active operation.
- Production monitor reported MONITORING.
- Guardian registration socket was present.
- CPU and GPU telemetry continued to be collected.

Observed thermal state during the preceding monitoring session:

- CPU package approximately 55–57°C.
- GPU edge approximately 57–61°C.
- GPU junction approximately 63–78°C.
- GPU memory approximately 62–66°C.
- GPU utilization briefly reached 100%.
- GPU fan speed approximately 1030–1045 RPM.

All reported sensors were NORMAL, with zero reported faults.

## Fan telemetry

The AMD GPU fan is readable through amdgpu hwmon.

The motherboard IT87952 controller exposes PWM channels but
currently reports zero RPM for its three fan inputs.

This is a separate investigation. No PWM settings were modified.

## Acceptance status

PASS: Production monitor activated.

PASS: Independent deadline guardian activated.

PASS: Shutdown authorization established.

PASS: IPC socket available.

PASS: Thermal monitoring operational.

PENDING: Live hardware-triggered shutdown acceptance.

PENDING: Physical UPS shutdown behavior.

## Safety and follow-up

The complete physical shutdown test is deferred until after the holiday.

No artificial thermal stress or threshold modification is part of
ordinary production operation.

The test plan is recorded separately in:

docs/testing/thermal-guardian-hardware-triggered-shutdown-test-plan-pots.md

UPS software integration must be inspected before the physical
shutdown acceptance test.

## Final assessment

Thermal Guardian is deployed and operational on Pots.

The remaining work is end-to-end acceptance of the complete
hardware-triggered privileged shutdown chain, not further development
of the underlying deadline or IPC mechanisms.

---

# PRODUCTION ACTIVATION UPDATE — 2026-11-25

**Host:** Pots
**Branch:** feature/thermal-guardian

## Production disposition: ACTIVATED

The production Thermal Guardian hardware-protection system has been activated.

### Active production components

- `thermal-guardian.service` — enabled; production hardware monitor.
- `thermal-guardian-deadline.service` — enabled; independent emergency deadline guardian.
- `thermal-guardian-poweroff.service` — authorized poweroff executor.
- Authenticated Unix-domain IPC between monitor and deadline guardian.
- Persistent, boot-scoped emergency deadline registration.
- Independent deadline enforcement and bounded operator override.
- Root-owned shutdown authority marker:
  `/etc/thermal-guardian/ENABLE-SHUTDOWN`
- Restricted sudoers authorization for the `thermal-guardian` account.

### Activation evidence

- Sudoers syntax validation: PASS.
- Shutdown authority marker ownership and permissions: PASS.
- Guardian authorization to read marker: PASS.
- Independent deadline service restart: PASS.
- Both production services subsequently entered startup activity.
- Production monitoring reported 29 discovered hardware sensors and zero reported sensor faults in the supplied observation.
- CPU package and core temperatures monitored.
- GPU edge, junction and memory temperatures monitored.
- GPU utilization and power telemetry operational.
- GPU fan RPM telemetry operational.
- PNY and Samsung NVMe temperatures monitored.

### Deferred end-to-end acceptance test

The final hardware-triggered shutdown acceptance test is deliberately deferred until after the holiday.

The planned test will exercise the complete production chain:

1. Temporarily lower the GPU junction trigger threshold using a controlled test configuration.
2. Start Asteroids@home to generate GPU load.
3. Observe actual thermal-trigger detection.
4. Verify authenticated IPC registration.
5. Observe the emergency countdown and operator shutdown challenge.
6. Exercise the bounded override where applicable.
7. Verify independent guardian shutdown dispatch.

The test will include explicit preparation and recovery arrangements.

Production monitoring remains active pending this test.

### Separate future work

Additional fan telemetry discovery, motherboard fan sensors, and fan-control investigations are separate workstreams.

They are not prerequisites for the present Thermal Guardian production activation.

### Current status

**PRODUCTION ACTIVE — HARDWARE-TRIGGERED SHUTDOWN ACCEPTANCE TEST PENDING.**

The final physical shutdown sequence has not yet been demonstrated on the production host.
