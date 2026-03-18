# ATLAS Orphan Process Problem

*Applies to: Einstein@Home ATLAS tasks on BOINC 8.x, Linux with CVMFS*

---

## The Problem

When running Einstein@Home on a system with LHC@home ATLAS tasks, you may observe one or more CPU
cores permanently pegged at 100% even after stopping the BOINC client. The processes responsible
are not visible in BOINC Manager, cannot be killed by stopping boinc-client, and survive across
BOINC restarts indefinitely.

This is not a BOINC bug. It is a consequence of how ATLAS jobs execute via CVMFS.

---

## Root Cause: CVMFS Process Re-parenting

ATLAS tasks (run by LHC@home, not Einstein@Home — despite the binary coming from Einstein's CVMFS
mount) execute through a chain of wrappers that ultimately invoke binaries from:

```
/cvmfs/atlas.cern.ch/...
```

At some point in this wrapper chain, a subprocess gets re-parented to **PID 1** (systemd/init).
This is a known behavior of certain CVMFS-hosted execution environments: the wrapper detaches
from its parent deliberately or as a side effect of the execution model.

Once re-parented to PID 1, the process is:

- **Outside BOINC's process tree** — `get_descendants()` walking the process tree from the
  boinc-client PID will never find it
- **Outside the boinc-client cgroup** — systemd's cgroup cleanup on service stop does not
  affect it
- **Invisible to BOINC Manager** — it does not appear in the Tasks list
- **Consuming real CPU** — typically 200-300% CPU (multi-threaded), running as root

The specific process observed:

```
python runargs.EVNTtoHITS.py
```

This is a GEANT4-based particle detector hit simulation — an ATLAS event generation step that
converts collision events (`EVNT`) to detector hit patterns (`HITS`). It runs multi-threaded and
is genuinely compute-intensive.

---

## Why `KillMode=process` Makes It Worse

The default BOINC client systemd drop-in often uses `KillMode=process`, which sends the stop
signal only to the main boinc process. Any children — including orphaned CVMFS processes — are
untouched.

Even `KillMode=control-group` (which nukes the entire cgroup on service stop) does not help for
processes that have already escaped the cgroup via re-parenting. By the time you stop boinc-client,
the ATLAS process is living under PID 1's cgroup, not boinc-client's.

---

## Detection

### Why standard BOINC process tree walking fails

A typical affinity or monitoring script walks descendants from the boinc-client PID:

```bash
get_descendants() {
    local parent=$1
    local children
    children=$(pgrep -P "$parent" 2>/dev/null)
    for child in $children; do
        echo "$child"
        get_descendants "$child"
    done
}
```

This correctly finds all processes with boinc-client as an ancestor. An orphaned ATLAS process
has PID 1 as its parent — it will never appear in this traversal.

### Pattern-based detection

The fix is to supplement tree-walking with name-pattern matching:

```bash
get_atlas_pids() {
    pgrep -f "runargs\|EVNTtoHITS\|AtlasG4\|Sim_tf\|Gen_tf\|python.*atlas\|python.*cern" 2>/dev/null
}
```

This catches the known ATLAS process name patterns regardless of their position in the process
tree. The two lists are then merged and deduplicated:

```bash
mapfile -t ALL_DESCENDANTS < <({ get_descendants "$CLIENT_PID"; get_atlas_pids; } | sort -u)
```

This approach is defensive: it catches orphans that have already escaped, not just processes
that are currently attached to BOINC.

---

## Fixes Applied

### 1. `KillMode=control-group` in boinc-client drop-in

```ini
# /etc/systemd/system/boinc-client.service.d/docker-dep.conf
[Service]
KillMode=control-group
```

**Why:** When boinc-client is stopped via systemctl, this nukes the entire cgroup including any
grandchildren that have not yet escaped. It's most effective early in a session before CVMFS
re-parenting has had time to occur. For long-running sessions, it's partially effective — better
than `KillMode=process` but not a complete solution.

**Caveat:** Only applies when BOINC is started via `systemctl start boinc-client`. If BOINC is
started manually (e.g. `sudo boinc --redirectio &`), the cgroup management is different and
this setting is advisory only.

### 2. Pattern-based detection in `boinc_affinity.sh`

See Detection section above. This allows the affinity script to manage and renice orphaned ATLAS
processes even after they've escaped BOINC's process tree, preventing them from monopolising
cores unmanaged.

### 3. Startup cleanup in `start.sh`

```bash
sudo pkill -f "runargs.EVNTtoHITS" 2>/dev/null
sudo pkill -f "EVNTtoHITS" 2>/dev/null
```

Added at the top of `start.sh`, before boinc is launched. Eliminates any orphans left over from
the previous session before BOINC creates new workers. Requires sudo because orphaned ATLAS
processes run as root.

---

## Known Remaining Limitations

**Long-running sessions:** If BOINC runs for hours without restart, CVMFS re-parenting will
eventually occur mid-session. The affinity script's `get_atlas_pids()` will detect and manage
the escaped process, but the process will survive a `systemctl stop boinc-client` until the next
`start.sh` execution kills it explicitly.

**Process name gaps:** The `get_atlas_pids()` pattern list covers known ATLAS process names as
of the time of writing. Future ATLAS task types may use different binary or script names. If
you observe unmanaged high-CPU processes from `/cvmfs/atlas.cern.ch/`, add their names to the
pattern list.

**Affinity script binary name logging:** Orphaned ATLAS processes run as root. The
`get_binary_name()` function reads `/proc/<pid>/exe`, which requires the affinity script to run
as root to resolve symlinks for root-owned processes. Without root, the binary name shows as
empty string `''` in log output. This is cosmetic — pinning and renicing still work correctly
via PID.

**`renice` on root-owned processes:** `renice` on a process owned by root requires root
privileges. The affinity script must run with `AmbientCapabilities=CAP_SYS_NICE` (set in the
systemd unit) or as root to successfully renice ATLAS orphans.

---

## Diagnostic Commands

Identify escaped ATLAS processes:
```bash
pgrep -af "runargs\|EVNTtoHITS\|AtlasG4\|Sim_tf\|Gen_tf" 
```

Check parent PID (expect 1 for an orphan):
```bash
ps -o pid,ppid,user,stat,pcpu,comm -p <PID>
```

Confirm cgroup membership (orphan will be under init, not boinc-client):
```bash
cat /proc/<PID>/cgroup
```

Manual kill:
```bash
sudo pkill -f "runargs.EVNTtoHITS"
```

---

## Summary

| Layer | Approach | Effectiveness |
|---|---|---|
| `KillMode=control-group` | Cgroup sweep on service stop | Partial — misses already-escaped processes |
| `get_atlas_pids()` in affinity script | Pattern-based detection | Effective for management/renicing |
| `pkill` in `start.sh` | Cleanup before each session | Effective — clears prior session orphans |

No single fix is complete. The three together provide acceptable containment: orphans from a
previous session are cleared on startup, new orphans are detected and managed by the affinity
script mid-session, and the cgroup setting provides a best-effort cleanup on shutdown.
