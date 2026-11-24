# Pots — Thermal Guardian observation validation

Date: 2026-11-24

## Environment

- Intel Core Ultra 5 245K
- AMD Radeon RX 9060 XT
- Kubuntu
- Einstein@home and MilkyWay@home
- GPU power cap: 120 W
- CPU package limits: unchanged
- GPU cooling: factory automatic control
- Poll interval: 1 second
- Journal status interval: 10 seconds
- Rolling diagnostic history: 300 seconds

## Overnight results

- PASS: 4052 NORMAL thermal reports.
- PASS: No recorded thermal warnings or emergencies.
- PASS: No recorded required-sensor faults.
- PASS: No guardian service restarts.
- PASS: No emergency diagnostic reports required.
- PASS: No swap use at morning inspection.
- PASS: GPU power cap retained.

## Archived evidence

~/thermal-guardian-validation/2026-11-24/overnight.log.gz

SHA256:
fa9e241f55896c8e0533f427244ef6bf95ad0b9312816c1921dca065b6fa5301

## Fan monitoring

AMDGPU tachometer, target RPM and PWM are exposed.
Zero RPM is normal during low-temperature operation.

Advanced gpu_od/fan_ctrl directory is unavailable.

ITE IT87952E controller exposes three tachometers
and three PWM channels. All tachometers report zero.
Physical channel mapping remains unverified.

No fan-control values were modified.

## Limitations

Observation only. Automatic shutdown is disabled.
Desktop alarm is not yet integrated.
Diagnostic collection is synchronous.
Motherboard fan readings are not trusted for protection.
Journal snapshots do not preserve all one-second readings.
