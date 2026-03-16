# STARTUP_SEQUENCE.md
# BOINC Startup and Shutdown Sequence — pots

*System: Kubuntu, 14-core AMD, BOINC 8.2.8*
*User: pepper | BOINC data dir: /var/lib/boinc-client/*

---

## Overview

BOINC on pots is started **manually** via `~/start-boinc-procedure`, not via
`systemctl start boinc-client`. This is a deliberate architectural decision with
specific consequences documented below.

---

## Why Manual Start, Not systemd?

The systemd `boinc-client.service` unit exists and is installed, but is not used
to start BOINC. Two reasons:

1. **Orphan cleanup must happen before BOINC starts.** ATLAS jobs (Einstein@Home,
   via CVMFS) can survive BOINC restarts as root-owned orphan processes. These
   must be killed before a new BOINC session begins, otherwise the affinity script
   inherits stale processes from the previous session. The systemd unit has no
   mechanism for this pre-start cleanup.

2. **`KillMode=control-group` only works when BOINC is started via systemctl.**
   The drop-in at `/etc/systemd/system/boinc-client.service.d/docker-dep.conf`
   sets `KillMode=control-group` to nuke CVMFS-escaped processes when BOINC stops.
   This cgroup management only applies to processes started within that unit's
   cgroup. A manually started boinc process is in a different cgroup and the
   setting has no effect on it.

The tradeoff: manual startup gives full control over the sequence at the cost of
losing automatic cgroup management for ATLAS orphans. The affinity script's
`get_atlas_pids()` function and the start script's pkill commands compensate for
this.

---

## Why Does boinc Run as Root?

```bash
sudo boinc --redirectio &
```

BOINC is started with sudo, running as root. This is intentional:

- `/var/lib/boinc-client/` and its contents are owned by the `boinc` system user.
  Running as root bypasses permission issues when multiple tools (boinccmd, boinc
  daemon, janitor services) need concurrent access.
- Docker container management for LHC@home tasks requires root-level access.
- Killing ATLAS orphan processes (owned by root via CVMFS re-parenting) requires
  root.

The "correct" approach would be running boinc as the `boinc` system user (uid 122,
gid 127) as the systemd unit does. This is a known limitation of the manual startup
approach — acceptable in a single-user homelab context, not recommended in a
multi-user or security-sensitive environment.

**Implication for group membership:** Since boinc runs as root, it is implicitly
a member of all groups. The `vboxusers` group membership added to the `boinc`
system user (`sudo usermod -aG vboxusers boinc`) only takes effect if BOINC is
ever switched to running as the `boinc` system user.

---

## Why Does boincmgr NOT Use sudo?

```bash
boincmgr &
```

`boincmgr` runs as `pepper` (the desktop user) without sudo. It connects to the
running boinc daemon via the GUI RPC interface rather than accessing files directly.
Giving it root is unnecessary and would cause X11/KDE display issues.

---

## boinccmd Authentication — The Working Directory Quirk

```bash
(cd /var/lib/boinc-client && boinccmd --set_run_mode auto)
```

`boinccmd` looks for `gui_rpc_auth.cfg` in the **current working directory**.
The symlink at `/var/lib/boinc-client/gui_rpc_auth.cfg` points to the actual
file at `/etc/boinc-client/gui_rpc_auth.cfg`, but boinccmd doesn't follow
symlinks at arbitrary paths — it only reads from CWD.

Running `boinccmd` from any other directory produces:
```
gui_rpc_auth.cfg exists but can't be read
```
even though the file is accessible. Always wrap boinccmd calls in the subshell
pattern above.

Do **not** use `--passwd $(cat /path/to/gui_rpc_auth.cfg)` — it's fragile and
exposes the password in the process list.

---

## start-boinc-procedure — Annotated

```bash
#!/bin/bash

# 1. Kill ATLAS orphans from previous session before starting
#    runargs.EVNTtoHITS.py processes survive BOINC restarts via CVMFS re-parenting
#    and must be cleaned up manually when not using systemd cgroup management
sudo pkill -f "runargs.EVNTtoHITS" 2>/dev/null
sudo pkill -f "EVNTtoHITS" 2>/dev/null

# 2. Start boinc daemon as root (see "Why root?" above)
#    --redirectio: redirects stdout/stderr to /var/lib/boinc-client/stdoutdae.txt
#    & : background — shell returns immediately
sudo boinc --redirectio &

# 3. Wait for daemon to initialize before boincmgr connects
sleep 3

# 4. Start GUI as desktop user (no sudo — connects via RPC)
boincmgr &

# 5. Set run mode to auto (CWD subshell pattern required — see above)
(cd /var/lib/boinc-client && boinccmd --set_run_mode auto)

# 6. Start affinity manager last — boinc workers need time to spawn first
sudo systemctl start boinc-affinity.service
```

---

## stop-boinc-procedure — Annotated

```bash
#!/bin/bash

# 1. Tell BOINC to stop accepting new work and checkpoint running tasks
(cd /var/lib/boinc-client && boinccmd --set_run_mode never)

# 2. Allow in-flight tasks to checkpoint cleanly
sleep 10

# 3. Stop affinity manager first — no point reassigning cores during shutdown
sudo systemctl stop boinc-affinity.service

# 4. Kill GUI and daemon
#    sudo required: boinc runs as root, pkill without sudo has no effect
sudo pkill boincmgr
sudo pkill boinc

# 5. Clean up ATLAS orphans that escaped the process tree
sudo pkill -f "runargs.EVNTtoHITS" 2>/dev/null
sudo pkill -f "EVNTtoHITS" 2>/dev/null
```

---

## Required Group Memberships — boinc System User

For full LHC@home functionality, the `boinc` system user requires:

| Group | Purpose |
|-------|---------|
| `boinc` (primary) | BOINC data directory access |
| `video` | GPU access for Einstein@Home OpenCL tasks |
| `render` | AMD GPU render access |
| `docker` | LHC@home ATLAS tasks via Docker |
| `vboxusers` | LHC@home CMS tasks via VirtualBox |

Check with: `id boinc`

Add missing groups: `sudo usermod -aG vboxusers,docker boinc`

**Note:** These group memberships only take effect for the boinc daemon if it is
started as the `boinc` system user. When started as root (current setup),
Docker and VBox access is granted implicitly via root privileges.

---

## Troubleshooting

**boinccmd fails with auth error:**
```bash
# Wrong — run from arbitrary directory
boinccmd --set_run_mode auto

# Right — subshell to correct CWD
(cd /var/lib/boinc-client && boinccmd --set_run_mode auto)
```

**pkill has no effect on boinc:**
```bash
# Check if boinc is running as root
ps aux | grep boinc | grep -v grep
# If USER column shows root, pkill requires sudo
sudo pkill boinc
```

**Affinity service dies when boinc restarts:**
The `boinc-affinity.service` drop-in clears `BindsTo=` and sets `Restart=always`
for this exact reason. If it's not restarting, check:
```bash
systemctl status boinc-affinity.service
journalctl -u boinc-affinity.service -n 20
```
