# BOINC Administration Timeline — pots
*Chronological troubleshooting and development history*
*Machine: Kubuntu, 14-core AMD, 30.8 GiB RAM, AMD GPU, BOINC 8.2.8*
*Projects: Einstein@Home, LHC@home, MilkyWay@home, Asteroids@home*

---

## Phase 1 — Initial Setup & Core Load Imbalance
**~Late February 2026**

### Problem: CPU load concentrated on 2-4 cores
- Cores reaching 68-71°C while other cores sat idle
- Thermal hotspots, uneven hardware wear

### Root Cause
Two conflicting BOINC instances running simultaneously:
- A systemd service running as the `boinc` user from `/var/lib/boinc-client/`
- A manager-launched instance running as `pepper` from `/home/pepper/`

The `pepper` instance was handling all active work in `/home/pepper/slots/` while the systemd service was largely dormant with stale slots.

### Solution
- Disabled the systemd service entirely
- Established `pepper`'s boincmgr-launched instance as canonical
- Developed `boinc_affinity.sh` — a bash script for CPU affinity management using proportional core allocation based on CPU usage

### Script Evolution
The affinity script went through several iterations:
1. Leaf process detection → incorrectly targeted utility processes (gawk, sleep)
2. CPU usage-based detection with process-level pinning → correct approach
3. Per-thread pinning → excessive overhead, abandoned
4. **Final: proportional core allocation** — processes consuming more CPU receive more cores, 20% CPU threshold filters monitoring utilities

### Outcome
Successful thermal distribution across all cores. Temps reduced to 26-53°C range. BOINC configured with 80% CPU usage limits.

---

## Phase 2 — LHC@home Docker Compatibility Crisis
**~February 16-23, 2026**

### Problem: LHC@home computation errors after Docker upgrade
All LHC@home tasks failing with "computation error." No credits awarded. Tasks initially dying immediately, later running to 100% then failing.

### Root Cause
Switch from `docker.io` (v27.5.1) to `docker-ce` (v29.2.1) on February 16th. Docker 29 introduced stricter default security profiles. Specific failure: `mount: /var/www/lighttpd: cannot mount tmpfs read-only` — the container lacked `CAP_SYS_ADMIN` needed to mount tmpfs inside the container. Lighttpd couldn't set up its working directory, so completed simulations couldn't serve their results. Also: output files owned as `root:root` instead of `boinc:boinc`, preventing BOINC from moving `output.tgz` from slot directories to project directories.

### Debugging Path
- Verified not AppArmor (no denial logs)
- Verified not Landlock
- Verified not seccomp (unconfined test failed to fix it)
- Confirmed capabilities issue: syscall allowed but `CAP_SYS_ADMIN` missing
- Discovered `docker_container_options` in `cc_config.xml` ignored in BOINC 8.2.8

### Solution
Two-part fix:
1. **Docker wrapper script** at `/usr/bin/docker` that intercepts container creation and injects `--privileged` flag
2. **Systemd service** that periodically `chown`s output files back to `boinc:boinc`

### Outcome
LHC@home tasks completing successfully with proper upload and credit allocation. Bug reports filed on LHC@home forums and BOINC GitHub documenting the docker-ce compatibility issue.

---

## Phase 3 — Global Preference Override Mystery
**~February 18, 2026**

### Problem: BOINC ignoring local CPU limits
Local preferences set to 40% CPUs "in use" / 80% "not in use" — but BOINC running at 100% regardless.

### Root Cause
Three competing preference layers:
- **Web prefs (global_prefs.xml)** from Einstein@Home containing a "home" venue with `max_ncpus_pct=100`, `cpu_usage_limit=100`
- **Local override (global_prefs_override.xml)** — the GUI settings
- BOINC sources prefs from the most recently updated project — venue-specific web prefs were winning

### Solution
Logged into all five project websites, set computing preferences to "green" on each. Updated each project in BOINC Manager to make them sync. Removed "home" venue override from Einstein@Home account.

### Key Learning
BOINC uses web prefs from whichever project was most recently updated as the "source project." Set matching preferences on ALL projects to avoid conflicts when any project re-syncs.

---

## Phase 4 — Systemd Shutdown Race Condition
**~February 25, 2026**

### Problem: Projects disappearing after reboot
Asteroids@home and MilkyWay@home vanished from project list after reboot, despite only being suspended.

### Root Cause
Two issues:
1. `gstate.init() failed` — `client_state.xml` corrupted during shutdown (BOINC killed mid-write)
2. Systemd hit `final-sigterm` timeout and sent SIGKILL to running LHC `runpilot2-wrapper` processes before BOINC could flush state to disk

### Solution
```ini
# /etc/systemd/system/boinc-client.service.d/docker-dep.conf
[Unit]
After=docker.service
Requires=docker.service

[Service]
TimeoutStopSec=120
KillMode=process
```

Re-attached lost projects manually via `boinccmd --project_attach`.

### Key Learning
`KillMode=process` was correct at the time — it allows BOINC to clean up children before dying. Later changed to `control-group` to address the ATLAS orphan problem (see Phase 6).

---

## Phase 5 — boinc-affinity.service Implementation
**~February 27, 2026**

### Problem: Affinity script not persistent
Script (`boinc_affinity.sh`) needed to run continuously as a daemon rather than one-shot, to catch newly spawned workers.

### Solution
Created `/etc/systemd/system/boinc-affinity.service`:
```ini
[Unit]
Description=BOINC CPU Affinity Manager
After=boinc-client.service
BindsTo=boinc-client.service

[Service]
Type=simple
ExecStartPre=/bin/sleep 5
ExecStart=/usr/local/bin/boinc_affinity.sh
Restart=on-failure
RestartSec=15
AmbientCapabilities=CAP_SYS_NICE
CapabilityBoundingSet=CAP_SYS_NICE
```

### Problem Discovered
`BindsTo=boinc-client.service` caused affinity service to die whenever boinc-client restarted for scheduler cycles. `Restart=on-failure` didn't resurrect it because SIGTERM = clean exit, not failure.

### Fix
Added drop-in override:
```ini
# /etc/systemd/system/boinc-affinity.service.d/override.conf
[Unit]
After=boinc-client.service
BindsTo=

[Service]
Restart=always
RestartSec=15
```

`BindsTo=` (empty) explicitly clears the directive from the main unit.

---

## Phase 6 — ATLAS Orphan Problem
**March 1, 2026**

### Problem: One core permanently pegged at 100% regardless of active projects
Even after stopping boinc-client, one core remained maxed out.

### Root Cause
**ATLAS jobs escape the BOINC process tree.** Einstein@Home ATLAS tasks run through CVMFS (`/cvmfs/atlas.cern.ch/...`) and at some point in the wrapper chain a process gets re-parented to PID 1 (init), making it invisible to `get_descendants()` in the affinity script. These orphaned processes survive BOINC client restarts entirely.

Specifically: `python runargs.EVNTtoHITS.py` — an ATLAS event simulation running as root via CVMFS, consuming 200-300% CPU, completely detached from BOINC's process tree.

### Contributing Factor
`KillMode=process` in the boinc-client drop-in meant only the main boinc process was killed on stop — CVMFS-escaped children were untouched.

### Solution — Two Parts

**1. KillMode fix** — changed to `control-group` in docker-dep.conf:
```ini
[Service]
KillMode=control-group
```
This nukes the entire cgroup including grandchildren when BOINC stops. (Note: only effective when BOINC is started via systemctl)

**2. Affinity script patch** — added `get_atlas_pids()` function to cast a wider net:
```bash
get_atlas_pids() {
    pgrep -f "runargs\|EVNTtoHITS\|AtlasG4\|Sim_tf\|Gen_tf\|python.*atlas\|python.*cern" 2>/dev/null
}
```
And merged into the main worker detection:
```bash
mapfile -t ALL_DESCENDANTS < <({ get_descendants "$CLIENT_PID"; get_atlas_pids; } | sort -u)
```

**3. start.sh cleanup** — added pkill at top to eliminate orphans from previous sessions:
```bash
sudo pkill -f "runargs.EVNTtoHITS" 2>/dev/null
sudo pkill -f "EVNTtoHITS" 2>/dev/null
```

---

## Phase 7 — Core Rotation Implementation
**March 1, 2026**

### Problem: Affinity script always assigns same 1-2 cores to high-load processes
The proportional allocator always started `core_cursor` at 0, so heavy processes (ATLAS at 200-300%) always landed on cores 0-1. Electromigration and wear accumulate on the same physical cores over time.

### Solution
Added rotation counter to `boinc_affinity.sh`:
```bash
ROTATION_STEP=2        # cores to advance each cycle
ROTATION_COUNTER=0     # tracks current offset
```

Starting position shifts each cycle:
```bash
local core_cursor=$(( ROTATION_COUNTER % TOTAL_CORES ))
```

Counter advances at end of each loop:
```bash
ROTATION_COUNTER=$(( ROTATION_COUNTER + ROTATION_STEP ))
```

Script now reassigns cores every cycle regardless of change detection, driving continuous rotation.

Also added `renice -n 19` alongside every `taskset` call to ensure heavy workers stay low priority.

### Outcome
Core assignment window rotates 2 positions every 10 seconds, completing a full cycle across all 14 cores in 70 seconds. Thermal load visibly migrates around the chip. CPU history graph shows all cores participating evenly over time.

---

## Phase 8 — Startup Sequence Refinement
**March 1, 2026**

### Problem: boinccmd authentication failure when run from wrong directory
`boinccmd --set_run_mode auto` failing with "gui_rpc_auth.cfg exists but can't be read."

### Root Cause
`boinccmd` looks for `gui_rpc_auth.cfg` in the **current working directory**, not by following the symlink at `/var/lib/boinc-client/gui_rpc_auth.cfg → /etc/boinc-client/gui_rpc_auth.cfg`. Must be run from `/var/lib/boinc-client/`.

### Solution
Subshell pattern in start.sh:
```bash
(cd /var/lib/boinc-client && boinccmd --set_run_mode auto)
```

### Final start.sh
```bash
#!/bin/bash
sudo pkill -f "runargs.EVNTtoHITS" 2>/dev/null
sudo pkill -f "EVNTtoHITS" 2>/dev/null
sudo boinc --redirectio &   # needs root for /var/lib/boinc-client
sleep 3
boincmgr &                  # runs as your user - no sudo needed
(cd /var/lib/boinc-client && boinccmd --set_run_mode auto)
sudo systemctl start boinc-affinity.service
```

---

## Known Remaining Issues

- **BOINC started manually, not via systemctl** — `KillMode=control-group` in boinc-client service is advisory only; ATLAS orphans can still occur if a session runs long enough for CVMFS to re-parent processes
- **Affinity script loses worker names** — `get_binary_name()` can't read `/proc/<root_pid>/exe` without sudo, so ATLAS processes show as `''` in logs (cosmetic only)
- **MilkyWay and LHC taking turns** — BOINC scheduler round-robins between them because both want most of the machine; `app_config.xml` per-project CPU limits could allow true coexistence
- **boincmgr SVG warnings** — `libpixbufloader-svg-CRITICAL: rsvg_handle_get_pixbuf_sub: assertion 'handle != NULL' failed` — cosmetic, missing icon assets in BOINC manager build
