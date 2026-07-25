# BOINC Administration Timeline — pots
*Chronological troubleshooting and development history*
*Machine: Kubuntu, Intel Core Ultra 5 245K, 30.8 GiB RAM, AMD GPU, BOINC 8.2.8*
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
Bug reports and community documentation deferred. Forum posts and BOINC GitHub issue filed March 16, 2026 (see Phase 9).
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

---

## Phase 9 — Docker Wrapper Overwrite & VirtualBox Group Fix
**March 16, 2026**

### Problem 1: LHC@home computation errors after docker-ce update

All LHC@home tasks failing with computation errors. Project stopped requesting
new tasks (BOINC automatic backoff after consecutive failures).

### Root Cause
`apt upgrade` updated docker-ce from 29.2.1 → 29.3.0, overwriting the wrapper
script at `/usr/bin/docker` with the real docker binary. The `--privileged`
injection was no longer happening, causing the same tmpfs mount failure as the
original Phase 2 issue.

### Solution — dpkg-divert for permanent protection

Previous approach (apt-mark hold) prevents upgrades but doesn't survive
`apt install docker-ce` or intentional unhold. Replaced with `dpkg-divert`:

```bash
# Register divert — future docker-ce installs go to docker.real
dpkg-divert --add --no-rename --divert /usr/bin/docker.real /usr/bin/docker

# Wrapper stays at /usr/bin/docker, updated real binary lands at /usr/bin/docker.real
```

Verified by reinstalling docker-ce with `apt-get install --reinstall docker-ce`
and confirming wrapper survived intact. The docker_wrapper.sh was also committed
to the repo (previously missing).

**Deployment note for other admins:**
- Deploy wrapper to `/usr/bin/docker`
- Move real binary to `/usr/bin/docker.real`
- Register divert: `dpkg-divert --add --no-rename --divert /usr/bin/docker.real /usr/bin/docker`
- Remove divert: `dpkg-divert --remove --no-rename /usr/bin/docker`

---

### Problem 2: boinc user missing from vboxusers group

Investigation of LHC@home's dual runtime (Docker for ATLAS tasks, VirtualBox for
CMS tasks) revealed the `boinc` system user was not in the `vboxusers` group.
CMS tasks requiring VBoxHeadless would fail to launch.

Confirmed: `sudo -u boinc VBoxManage list vms` returned permission error.

Groups present: `boinc video render docker` — `vboxusers` missing.

### Solution
```bash
sudo usermod -aG vboxusers boinc
```

Restarted BOINC to pick up new group membership. Verified with `id boinc`.

**Note:** Since boinc is currently started as root (via `sudo boinc --redirectio`),
group membership is academic for the current setup — root bypasses group checks.
This fix becomes relevant if BOINC is ever switched to running as the `boinc`
system user.

---

### Problem 3: stop-boinc-procedure not killing boinc or boincmgr

`pkill boinc` and `pkill boincmgr` in the stop script had no effect.

### Root Cause
Script was being run as `pepper` without sudo. Since `boinc` runs as root
(started via `sudo boinc --redirectio`), an unprivileged pkill cannot signal it.

Additionally the script was using `--passwd $(cat /path/to/gui_rpc_auth.cfg)`
for boinccmd authentication rather than the correct subshell CWD pattern.

### Solution
Added `sudo` to all pkill calls. Reverted boinccmd to the established subshell
pattern:
```bash
(cd /var/lib/boinc-client && boinccmd --set_run_mode never)
```

---

### Key Learnings from Phase 9

- `dpkg-divert` is the correct long-term solution for owning a system binary that
  packages want to manage. `apt-mark hold` is a temporary measure only.
- LHC@home requires the boinc user in **both** `docker` and `vboxusers` groups
  for full functionality — ATLAS tasks use Docker, CMS tasks use VirtualBox. This
  is not documented clearly anywhere in the LHC@home or BOINC documentation.
- When boinc runs as root, `pkill` without sudo silently fails — the stop script
  must use `sudo pkill` for both `boinc` and `boincmgr`.

---

### Community Outreach — March 16, 2026

Following resolution of the Phase 9 issues, bug reports and community documentation
were filed:

**BOINC GitHub Issue:**
- `docker_container_options` in cc_config.xml silently ignored — no way to pass
  `--privileged` to LHC@home containers (BOINC 8.2.8)
- URL: https://github.com/BOINC/boinc/issues/6914

**LHC@home Forum Posts (pending):**
- Thread 1: docker-ce 29.x breaks ATLAS tasks: tmpfs mount failure and the fix
- Thread 2: LHC@home silent task failures: boinc user missing docker and vboxusers group membership
- Thread 3: ATLAS jobs survive BOINC client restart: CVMFS orphan processes pegging CPU cores and the fix

---

## Operational Note — March 30, 2026

### Project Consolidation
All projects removed from pots except LHC@home. Einstein@Home, MilkyWay@home, and Asteroids@home have been detached. LHC@home is now the sole active project.

### Preference Tuning
Two values updated in `global_prefs_override.xml`:
- `suspend_cpu_usage`: 25% → 35% — prevents BOINC suspending during normal desktop use
- `ram_max_used_busy_pct`: 50% → 25% (~7.7 GiB ceiling) — discourages scheduler from launching a second ATLAS task while one is already running

Both changes applied via `sed` and reloaded with `boinccmd --read_global_prefs_override`.

---

## Phase 10 — Project Consolidation & ATLAS Concurrency Lock
**March 31, 2026**

### Problem: LHC@home refusing to run alongside other projects
LHC@home posting computation errors; project reset required. Concurrent
ATLAS tasks (2x simultaneous) saturating CPU and exceeding RAM ceiling
despite `ram_max_used_busy_pct=25` (~7.7 GiB target). Observed 699%
combined CPU usage, 9.9 GiB RAM consumed.

### Decision
Removed all projects except LHC@home. RAM preference alone proved
insufficient as a concurrency guardrail for ATLAS tasks.

### Solution
Deployed `app_config.xml` to project directory with `max_concurrent 1`
for ATLAS app:
```xml
<app_config>
    <app>
        <name>ATLAS</name>
        <max_concurrent>1</max_concurrent>
    </app>
</app_config>
```

Note: `boinccmd --read_app_config` does not exist in BOINC 8.2.9.
`--get_app_config` returns "not found" error despite file being present
and readable — appears to be a client bug. Config confirmed active via
observed behavior: single ATLAS task running, others queued as "Waiting
to run." RAM stabilized at 7.5 GiB.

### Outcome
Single ATLAS task running at ~306% CPU across cores 12-13. Theory
Simulation tasks queued. GPU task requests suppressed (no Einstein@Home).
System stable.

---

## Phase 11 — Data Directory Ambiguity Fix
**April 2, 2026**

### Problem: start-boinc-procedure sometimes launched Einstein@Home
Running `./start-boinc-procedure` occasionally opened BOINC with the old
multi-project state (Einstein@Home, MilkyWay@home still present) instead
of the clean LHC-only configuration.

### Root Cause
`boinc` without `--dir` uses its CWD as the data directory. The script
launched boinc differently depending on invocation context, resolving to
either `/home/pepper/` (correct) or `/var/lib/boinc-client/` (stale).
Confirmed via `/proc/<pid>/cwd` symlink inspection.

Two separate `client_state.xml` files existed:
- `/home/pepper/client_state.xml` — LHC@home only (correct)
- `/var/lib/boinc-client/client_state.xml` — Einstein@Home + LHC + MilkyWay (stale)

The `boinccmd` subshell in both start and stop scripts also referenced
`/var/lib/boinc-client/` — wrong directory for `gui_rpc_auth.cfg`.

### Solution
- Added `--dir /home/pepper` to the `boinc` invocation in start-boinc-procedure
- Updated `boinccmd` subshell in both scripts to `cd /home/pepper`
- Renamed `/var/lib/boinc-client/client_state.xml` → `client_state.xml.stale`

### Key Learning
Always pin `--dir` explicitly in the boinc invocation. Never rely on CWD.
Diagnose data directory issues with `/proc/<pid>/cwd` + `grep master_url`
on candidate `client_state.xml` files.

---

## Phase 12 — Theory Simulation Docker Failures & Bug Filing
**April 5, 2026**

### Problem: Theory Simulation tasks stuck at 100%, never uploading
All LHC@home Theory Simulation tasks completing computation but never transitioning to upload state. Tasks showed 100% progress and "Running" status indefinitely — confirmed persisting overnight (12+ hours) without resolution.

### Root Causes Identified

**1. docker_wrapper_18 infinite loop on container exit**
When a Theory Simulation container finishes and exits, docker_wrapper_18 fails to detect the exit condition. Instead of collecting output and reporting completion, it enters an infinite loop issuing pause/unpause commands against the dead container:

When a Theory Simulation container finishes and exits, docker_wrapper_18 fails to detect the exit condition. Instead of collecting output and reporting completion, it enters an infinite loop issuing pause/unpause commands against the dead container. Error: "container is not running" / "Container is not paused" — repeated indefinitely. The wrapper has no handler for this condition.

**2. max_concurrent ignored for Docker tasks**
app_config.xml with max_concurrent=1 for the Theory app is completely ignored by BOINC 8.2.9. Tasks download and execute 9-10 simultaneously regardless. project_max_concurrent=1 also ignored. Both confirmed active via boinccmd --get_app_config.

**3. Containers stuck in Created state**
Some containers never progressed past "Created" status and were never started by the wrapper, leaving tasks permanently stuck with no CPU activity.

### Contributing Factor: Wrong chown service path
boinc-chown.service still targeting /var/lib/boinc-client/slots/ — the dead instance path. Corrected to /home/pepper/slots/.

### app_config.xml
Theory set to max_concurrent=0 (disabled) pending upstream fix. ATLAS entry removed — LHC@home no longer serves ATLAS tasks.

### Workaround Confirmed
Killing the wrapper process causes BOINC to immediately report "Computation for task X finished" and clean up correctly. Not sustainable at scale.

### Bug Filed
BOINC GitHub issue #6957 — docker_wrapper: infinite loop on container exit + max_concurrent ignored for Docker tasks. See docs/completion_watch.log for full task lifecycle capture.

### Key Learnings
- docker_wrapper is BOINC-supplied, not LHC@home code — bugs filed upstream
- LHC@home ships docker_wrapper_18; BOINC latest tagged release is dockerwrapper/17
- max_concurrent enforcement broken for Docker tasks in BOINC 8.2.9 — no local workaround available
- Theory Simulation disabled pending upstream fix; Einstein@Home + MilkyWay@home resumed

### Current Operational Status
LHC@home suspended pending resolution of BOINC issue #6957. Einstein@Home and MilkyWay@home re-enabled and running normally. GPU active on Einstein@Home OpenCL tasks. Will resume LHC@home Theory tasks once upstream docker_wrapper fix is available and deployed by LHC@home.

### GitHub Discussion Filed
BOINC GitHub Discussion #6958 — Proposal: Zero-Config Volunteer Computing for LHC@home
https://github.com/BOINC/boinc/discussions/6958

---

## Phase 13 — Kernel and BOINC State Recovery
**July 25, 2026**

### Kernel regression containment

Kernel `7.0.0-28-generic` hung after successful LUKS unlock and also showed
AMDGPU teardown failures during shutdown. Kernel `6.17.0-40-generic` booted
cleanly and was selected as the explicit GRUB default. Its exact packages were
marked manual to protect them from autoremove.

### BOINC data-directory consolidation

The historical root client under `/home/pepper` and the systemd client under
`/var/lib/boinc-client` had diverged. The former contained the intended
LHC-only project state; the latter contained stale Einstein, LHC, and MilkyWay
attachments. The LHC-only state was safely migrated into the service directory,
with the replaced tree retained for rollback.

The manual root-client workflow was retired. systemd now owns the entire client
control group, BOINC Manager connects to that client, and the affinity service
rotates at most four active CPUs across `0-11` while reserving `12-13`.

### SableLinux record import

The standalone repository now summarizes SableLinux BOINC 8.2.11 source-build
work, the manual `boincctl` layer, EliteBook validation, Z890 client/GPU
validation, and the custom-kernel readiness checkpoint for rootless LHC
containers. Ongoing Sable integration remains in `sablelinux/development` until
validated and promoted under `SYNC_POLICY.md`.
