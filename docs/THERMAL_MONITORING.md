# Thermal Monitoring

*Applies to: pots — Intel Core Ultra 5 245K, AMD GPU (amdgpu-pci-0300), Kubuntu*

---

## Overview

Sustained distributed computing workloads generate significant and continuous heat. On pots,
CPU cores regularly reach 70-90°C under full BOINC load and the AMD GPU runs at sustained
load for GPU-accelerated tasks. Knowing the sensor layout, normal operating ranges, and
critical thresholds for this specific hardware is essential for catching problems early.

---

## Sensor Layout

The system exposes sensors via the `lm-sensors` package. The relevant adapters are:

coretemp-isa-0000 — Intel CPU per-core temperatures. Reports individual core package
temperatures across all physical cores. On the Intel Core Ultra 5 245K, cores are numbered
0-1, 2-3, 4-5, 6-7, 8, 12, 16, 18, 20, 24, 28 (package IDs vary from logical core
numbers).

amdgpu-pci-0300 — AMD GPU temperatures and power. Reports:
- edge — GPU die edge temperature
- junction — GPU hotspot temperature (highest point on die, most relevant for throttling)
- mem — VRAM temperature
- fan1 — fan RPM
- PPT — Package Power Tracking in watts, against a cap

nvme-pci-0400 — NVMe SSD temperature (composite and sensor readings).

acpitz — ACPI thermal zone, motherboard ambient. Less precise than coretemp but useful
as a sanity check.

---

## Thresholds — Intel Core Ultra 5 245K

From the sensor output on this machine:

    high = 85°C    — thermal throttling begins approaching this point
    crit = 105°C   — critical threshold, emergency shutdown territory

Normal operating ranges under BOINC load on pots:

- Idle / light load: 28-38°C
- Moderate load (50-70% CPU): 45-60°C
- Full BOINC load (all cores): 60-80°C
- Peak observed under sustained ATLAS workload: ~80°C

Temperatures in the 70-80°C range are normal and expected during heavy distributed
computing. The thermal design of modern desktop CPUs accommodates sustained operation
up to the high threshold. Concern is warranted above 85°C sustained — check case
airflow, thermal paste, and whether the affinity rotation is functioning correctly.

---

## Thresholds — AMD GPU

From the sensor output on this machine:

    edge:      high = 100°C, hyst = -273°C (not meaningful), crit = 110°C
    junction:  high = 110°C, hyst = -273°C, crit = 115°C
    mem:       high = 115°C, crit = 120°C (emerg = -273°C)
    PPT:       cap = 100W

Normal operating ranges under BOINC GPU load:

- Einstein@Home OpenCL (GPU-assisted gravitational wave search): junction 60-70°C, PPT 50-65W
- Asteroids@home (GPU-heavy): junction 65-72°C, GPU utilisation at 100%, PPT 55-70W
- Idle: junction ~45°C

AMD GPU junction temperatures in the 60-75°C range are entirely normal. The junction
threshold of 110°C gives substantial headroom. GPU fan behaviour is automatic — the fan
will ramp up well before temperatures approach concerning levels.

---

## Monitoring Commands

Real-time sensor watch (updates every 1.5 seconds):

    watch -n 1.5 sensors -A

This is the primary monitoring tool. The -A flag suppresses adapter headers for cleaner
output. On pots the relevant blocks are coretemp-isa-0000 and amdgpu-pci-0300.

Single snapshot:

    sensors -A

GPU-specific detail (if sensors output is insufficient):

    cat /sys/class/drm/card0/device/hwmon/hwmon*/temp*_input

CPU per-core temperature via sysfs:

    paste <(cat /sys/devices/platform/coretemp.0/hwmon/hwmon*/temp*_label 2>/dev/null) \
          <(cat /sys/devices/platform/coretemp.0/hwmon/hwmon*/temp*_input 2>/dev/null)

BOINC GPU utilisation (AMD):

    cat /sys/class/drm/card0/device/gpu_busy_percent

---

## Interpreting the Affinity Script's Thermal Effect

The core rotation mechanism in boinc_affinity.sh is directly observable in the sensor
output. With ROTATION_STEP=2 and POLL_INTERVAL=10 on a 14-core system, the heaviest
process migrates through the full core range every 70 seconds.

In a `watch -n 1.5 sensors -A` session during heavy ATLAS load you will see individual
core temperatures rise and fall in a moving pattern rather than a static hot cluster.
Cores 0-1 may be hottest for 30-40 seconds, then cores 2-3 take over, and so on. This
is the rotation working as intended.

If you observe a static hot cluster of 2-4 cores that does not migrate, check whether
the affinity service is running:

    systemctl status boinc-affinity

---

## Thermal Alert Script

A simple one-liner to alert if any CPU core exceeds a threshold:

    sensors -A | awk '/Core/ {gsub(/[^0-9.]/, "", $3); if ($3+0 > 85) print "ALERT: " $0}'

This can be added to a cron job or systemd timer for background monitoring. Substitute
85 with your chosen alert threshold.

For the GPU junction temperature:

    python3 -c "
    import subprocess, re
    out = subprocess.check_output(['sensors', '-A']).decode()
    m = re.search(r'junction.*?\+(\d+\.\d+)', out)
    if m and float(m.group(1)) > 95:
        print(f'GPU junction ALERT: {m.group(1)}C')
    "

---

## Notes for Other Administrators

Sensor naming varies by hardware. Run `sensors -A` on your system first to identify
the correct adapter names and core labels before relying on any monitoring script.

On AMD Ryzen and Threadripper systems, the relevant adapter is typically k10temp rather
than coretemp. The Tctl/Tdie readings are the primary temperature metrics on those
platforms.

Junction temperature (also called Tjunction or hotspot) is the most meaningful GPU
temperature metric for throttling purposes, not the edge temperature. Always monitor
junction when assessing GPU thermal health.

The affinity script's core rotation provides passive thermal management as a side effect
of its primary purpose (even hardware wear). It is not a substitute for adequate case
airflow and CPU cooling. Sustained temperatures above 80°C under normal load suggest a
cooling problem that rotation alone cannot compensate for.
