# Scripts Inventory & Documentation Roadmap

---

## Scripts Inventory

### 1. `boinc_affinity.sh`
- **Purpose:** Continuously monitors BOINC worker processes and assigns CPU affinity masks proportionally based on CPU usage. Rotates the core assignment window every cycle to distribute thermal load across all cores evenly over time. Also detects ATLAS/CVMFS orphan processes that escape the BOINC process tree.
- **Location:** `/usr/local/bin/boinc_affinity.sh`
- **Status:** ✅ Current (v3 — with ATLAS detection + core rotation + renice)
- **Managed by:** `boinc-affinity.service`

---

### 2. `start.sh`
- **Purpose:** Full BOINC startup sequence — kills any lingering ATLAS orphans from previous sessions, starts boinc daemon as root, launches boincmgr as user, sets run mode to auto, starts affinity service.
- **Location:** `/home/pepper/start.sh`
- **Status:** ✅ Current
- **Contents:**
```bash
sudo pkill -f "runargs.EVNTtoHITS" 2>/dev/null
sudo pkill -f "EVNTtoHITS" 2>/dev/null
sudo boinc --redirectio &   # needs root for /var/lib/boinc-client
sleep 3
boincmgr &                  # runs as your user - no sudo needed
(cd /var/lib/boinc-client && boinccmd --set_run_mode auto)
sudo systemctl start boinc-affinity.service
sudo journalctl -u boinc-affinity.service -f
```

---

### 3. `stop.sh`
- **Purpose:** Graceful BOINC shutdown sequence.
- **Location:** `/home/pepper/stop.sh`
- **Status:** ✅ Current
- **Contents:**
```bash
#!/bin/bash

cd /home/pepper
boinccmd --host localhost --passwd $(cat /home/pepper/gui_rpc_auth.cfg) --set_run_mode never
sleep 10
pkill boincmgr
pkill boinc

sudo systemctl stop boinc-affinity.service
```

---

### 4. Docker wrapper (anonymous)
- **Purpose:** Intercepts `docker run` commands issued by BOINC and injects `--privileged` flag to allow tmpfs mounts inside LHC@home containers. Workaround for docker-ce 29.x compatibility issue with BOINC 8.2.8.
- **Location:** `/usr/bin/docker` (wraps real docker binary)
- **Status:** ✅ Current (active workaround pending upstream fix)

---

### 5. boinc output chown service (anonymous)
- **Purpose:** Periodically chowns LHC@home output files from `root:root` back to `boinc:boinc`, allowing BOINC to successfully move `output.tgz` from slot directories to project directories.
- **Location:** `/etc/systemd/system/` (service + timer)
- **Status:** ✅ Current (active workaround)

---

## Systemd Units

### `boinc-affinity.service`
- **Location:** `/etc/systemd/system/boinc-affinity.service`
- **Drop-in:** `/etc/systemd/system/boinc-affinity.service.d/override.conf`
- **Key settings:** `Restart=always`, `BindsTo=` (cleared), `AmbientCapabilities=CAP_SYS_NICE`

### `boinc-client.service.d/docker-dep.conf`
- **Location:** `/etc/systemd/system/boinc-client.service.d/docker-dep.conf`
- **Key settings:** `After=docker.service`, `Requires=docker.service`, `KillMode=control-group`

---

## Documentation To Create (Prioritized)

### Priority 1 — Core operational docs

**`docs/ATLAS_ORPHAN_PROBLEM.md`**
The single most surprising and underdocumented issue in this setup. Covers: how ATLAS jobs escape the BOINC process tree via CVMFS re-parenting, why `KillMode=process` is insufficient, the `get_atlas_pids()` detection approach, the start.sh pkill workaround, and known remaining limitations. Valuable to any BOINC admin running Einstein@Home ATLAS tasks.

**`docs/STARTUP_SEQUENCE.md`**
Full annotated startup and shutdown sequences. Covers: why BOINC runs as root, why boincmgr does not need sudo, the `gui_rpc_auth.cfg` symlink/directory quirk requiring `cd /var/lib/boinc-client`, the subshell pattern for boinccmd, why affinity service is started last, and graceful shutdown order.

**`docs/PREFERENCES.md`**
The three-layer BOINC preference system and how they conflict. Covers: local prefs vs web prefs vs venue-specific overrides, the "source project" mechanism, why setting preferences on one project can be overridden when another project syncs, and the procedure for locking preferences consistently across all projects.

---

### Priority 2 — Project-specific quirks

**`docs/LHC_DOCKER_COMPATIBILITY.md`**
The docker-ce 29.x / BOINC 8.2.8 incompatibility. Covers: the `tmpfs read-only` failure mode, the `root:root` output ownership issue, why `docker_container_options` in cc_config.xml is silently ignored in BOINC 8.2.8, the `--privileged` wrapper approach, the chown service workaround, and the filed bug reports. Essential reading before upgrading Docker on a BOINC system.

**`docs/AFFINITY_AND_ROTATION.md`**
How the CPU affinity manager works, why proportional allocation was chosen over equal distribution, the core rotation mechanism and its thermal rationale, script configuration parameters (POLL_INTERVAL, CPU_THRESHOLD, MIN_CORES, ROTATION_STEP), and how to tune for different workload profiles.

---

### Priority 3 — Reference docs

**`docs/SYSTEMD_CONFIGURATION.md`**
All systemd unit files and drop-ins with explanations. Covers: `BindsTo` vs `After` semantics, why `BindsTo=` (empty) is needed to clear inherited directives, `KillMode=control-group` vs `process` tradeoffs, `TimeoutStopSec` tuning, and `AmbientCapabilities` for non-root taskset operations.

**`docs/THERMAL_MONITORING.md`**
Sensor monitoring setup for AMD CPU + GPU. The `sensors -A` command for per-core temps, the `watch` one-liner for real-time monitoring, trip points and critical thresholds on this hardware, and the thermal alert script.

---

## Suggested First Commit Contents

```
sable-boinc_admin/
├── README.md                          ← write fresh
├── scripts/
│   ├── boinc_affinity.sh              ← copy from /usr/local/bin/
│   ├── start.sh                       ← copy from /home/pepper/
│   └── stop.sh                        ← copy from /home/pepper/
├── systemd/
│   ├── boinc-affinity.service         ← copy from /etc/systemd/system/
│   ├── boinc-affinity-override.conf   ← copy from .service.d/
│   └── boinc-client-docker-dep.conf   ← copy from boinc-client.service.d/
├── docs/
│   ├── TIMELINE.md                    ← this document
│   └── ATLAS_ORPHAN_PROBLEM.md        ← write next
└── config/
    ├── global_prefs_override.xml      ← copy from /var/lib/boinc-client/
    └── cc_config.xml                  ← copy from /etc/boinc-client/
```
