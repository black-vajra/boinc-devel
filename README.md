# boinc-devel

BOINC administration, configuration, and documentation for **pots** — a 14-core AMD Kubuntu workstation running multiple distributed computing projects simultaneously.

## System Profile

| Item | Detail |
|------|--------|
| Hostname | pots |
| OS | Kubuntu (KDE Plasma, X11) |
| CPU | 14-core AMD (7 physical × 2 threads) |
| RAM | 30.8 GiB |
| GPU | AMD (amdgpu-pci-0300, OpenCL) |
| BOINC | 8.2.8 |

## Active Projects

- **Einstein@Home** — gravitational wave / pulsar searches (CPU + AMD GPU via OpenCL)
- **LHC@home** — CERN particle physics simulations (Docker, CVMFS)
- **MilkyWay@home** — N-body galaxy fitting (CPU + GPU)
- **Asteroids@home** — asteroid shape modeling (CPU)

## Repository Structure
```
boinc-devel/
├── config/          # global_prefs_override.xml, cc_config.xml
├── docs/            # troubleshooting timeline and reference docs
├── scripts/         # boinc_affinity.sh, start/stop procedures
└── systemd/         # service units and drop-in overrides
```

## Key Issues Documented

- **CPU affinity and thermal management** — proportional core allocation with rotation to distribute thermal load across all 14 cores
- **ATLAS orphan processes** — Einstein@Home ATLAS tasks escape the BOINC process tree via CVMFS re-parenting; detection and cleanup approach documented
- **LHC@home / docker-ce 29.x incompatibility** — tmpfs mount failure and output file ownership workarounds
- **BOINC preference layer conflicts** — web prefs vs local override vs venue-specific settings

## docs/

| File | Contents |
|------|----------|
| TIMELINE.md | Chronological troubleshooting and development history |
| SCRIPTS_AND_DOCS.md | Scripts inventory and documentation roadmap |
| BOINC_Admin_Addendum_Mar2_2026.docx | Addendum covering Feb 28 – Mar 2, 2026 |

## Audience

Written for BOINC administrators running mixed CPU/GPU workloads on Linux, particularly those dealing with Docker-based tasks, CVMFS-dependent projects, or thermal management on multi-core systems.
