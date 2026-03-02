LHC@home — Configuration, Quirks, and Workarounds
System: pots (14-core AMD, Kubuntu, BOINC 8.2.8)
Last updated: March 2, 2026
Overview
LHC@home runs CERN particle physics simulations via Docker containers. On this system it required significant non-obvious configuration to achieve stable operation. This document covers every speciality configuration that was required, why it was needed, and what was done.

1. Docker Service Dependency
Problem
BOINC attempts to launch LHC@home task containers at startup. If Docker isn't running yet when boinc-client starts, tasks fail immediately.
Solution
Added a systemd drop-in at /etc/systemd/system/boinc-client.service.d/docker-dep.conf:
ini[Unit]
After=docker.service
Requires=docker.service
```

**Caveat:** On this system BOINC is started manually following the procedure shown in `~/start-boinc-procedure`, not via systemctl. This dependency is therefore advisory only.

---

## 2. docker-ce 29.x Incompatibility — tmpfs Mount Failure

### Background
On February 16, 2026, Docker was upgraded from `docker.io` v27.5.1 to `docker-ce` v29.2.1. All LHC@home tasks immediately began failing with "computation error."

### Root Cause
Docker 29 introduced stricter default security profiles. The specific failure:
```
mount: /var/www/lighttpd: cannot mount tmpfs read-only
LHC@home containers require CAP_SYS_ADMIN to mount tmpfs inside the container. Docker 29's default capability profile no longer grants this without explicit configuration.
Debugging Path
Ruled out before identifying root cause:

AppArmor — no denial logs
Landlock — not active on this kernel
Seccomp — --security-opt seccomp=unconfined did not fix it; confirmed capability issue not syscall
docker_container_options in cc_config.xml — silently ignored in BOINC 8.2.8 (see Section 4)

Solution — Docker Wrapper Script
A wrapper at /usr/bin/docker intercepts container creation and injects --privileged. Real binary moved to /usr/bin/docker.real.
Security note: --privileged grants full host capabilities. Acceptable here because containers originate from CERN. Monitor upstream for a proper fix.

3. Output File Ownership — root:root vs boinc:boinc
Problem
Tasks ran to 100% then failed at upload. BOINC could not move output.tgz from slot directories to project directories.
Root Cause
Docker 29 causes output files written inside containers to be owned root:root on the host instead of boinc:boinc. BOINC runs as the boinc user and cannot move root-owned files.
Solution — Chown Janitor Service
A systemd service + timer pair periodically corrects ownership. Runs every 2 minutes, targeting /var/lib/boinc-client/slots/ and /var/lib/boinc-client/projects/.

4. cc_config.xml docker_container_options — Silently Ignored
BOINC 8.2.8 does not implement the <docker_container_options> directive despite it being documented. It is parsed but never passed to the Docker invocation. The wrapper script in Section 2 exists because of this. Bug filed on BOINC GitHub.

5. ATLAS Tasks via CVMFS — Orphan Process Problem
Problem
ATLAS work units invoke binaries from CVMFS (/cvmfs/atlas.cern.ch/...) via runpilot2-wrapper, ultimately spawning python runargs.EVNTtoHITS.py. This process gets re-parented to PID 1, making it invisible to BOINC's process tree. Orphaned processes consume 200-300% CPU and survive BOINC client restarts entirely.
Solutions

KillMode=control-group in boinc-client drop-in — nukes entire cgroup on BOINC stop
pkill in start.sh — cleans up orphans from previous sessions at startup
Pattern-based detection in boinc_affinity.sh via get_atlas_pids()


6. KillMode Evolution
PhaseSettingReasonPhase 4 (Feb 25)KillMode=processAllow BOINC to flush state cleanly before dyingPhase 6 (Mar 1)KillMode=control-groupGuarantee CVMFS-escaped ATLAS processes are killed

Current Status (March 2, 2026)
ComponentStatusDocker wrapper (--privileged)✅ ActiveChown janitor service✅ ActiveKillMode=control-group✅ ActiveATLAS orphan pkill in start.sh✅ Activedocker_container_options in cc_config.xml❌ Silently ignoredLHC@home tasks completing + uploading✅ Confirmed stable

Upstream Bug Reports Pending

LHC@home forums — docker-ce 29.x / BOINC 8.2.8 tmpfs incompatibility
BOINC GitHub — docker_container_options silently ignored in BOINC 8.2.8
