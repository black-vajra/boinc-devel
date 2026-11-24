# Protected Thermal Guardian installation

Date: 2026-11-24
Host: pots
Kernel: 6.17.0-40-generic
Systemd: 255.4
Python: 3.12.3
Branch: feature/thermal-guardian
Previous checkpoint: f09ce2c

## Installation

Root-owned observation-only installation.

Directories:
 /usr/local/lib/thermal-guardian/ 0755
 /etc/thermal-guardian/           0750
 /var/lib/thermal-guardian/       0700
 /var/log/thermal-guardian/       0700

Installed files:
 thermal_guardian.py
 thermal_guardian_launcher.py
 pots.json

Python execution flags:
 -I -S -B

## Validation

PASS: Privileged hardware observation.
Exit status: 0.

PASS: Unauthorized entry point rejected.
Exit status: 1.

PASS: Synthetic temperature injection rejected.
Exit status: 1.

PASS: Unexpected additional arguments rejected.
Exit status: 1.

PASS: Restricted Python import paths.
PASS: Root ownership and file permissions.
PASS: Installed files match development sources.

## Restricted Python paths

/usr/lib/python312.zip
/usr/lib/python3.12
/usr/lib/python3.12/lib-dynload

Third-party and ROCm import paths excluded.

## Thermal baseline

CPU package: 35 C.
GPU edge: 46 C.
GPU junction: 51 C.
GPU memory: 48 C.
GPU power cap: 120 W.
All required sensors NORMAL.

## Limitations

Observation-only installation.
Shutdown backend not installed.
Authenticated IPC not implemented.
Production supervisor not installed.
Production recovery state not initialized.
BOINC dependency enforcement pending.
Privileged runtime directory not created.

Launcher restrictions do not constitute
a complete process security sandbox.

## Safety

No actual shutdown authority.
No hardware settings modified.
No BOINC service modifications.
Existing thermal observation service retained.
