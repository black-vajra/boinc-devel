# LHC@home Docker Compatibility

*Applies to: BOINC 8.x, docker-ce 29.x, Linux, LHC@home ATLAS tasks*

---

## Overview

Running LHC@home on a system with docker-ce 29.x requires three workarounds that are not
documented anywhere in the official BOINC or LHC@home setup guides:

1. A wrapper script to inject `--privileged` into container creation calls
2. A chown service to repair output file ownership
3. Correct group membership for the boinc user

Each is documented below. All three must be in place for tasks to complete and upload
successfully.

---

## Issue 1 — docker-ce 29.x Breaks tmpfs Mounts

### Symptom

After upgrading from `docker.io` (≤27.x) to `docker-ce` (29.x), all LHC@home ATLAS tasks
fail with "computation error." Tasks may die immediately or run to 100% completion then fail
at the upload stage.

The definitive error in the task's `stderr.txt`:

```
mount: /var/www/lighttpd: cannot mount tmpfs read-only
```

### Root Cause

Docker 29.x introduced stricter default security profiles. Containers launched without
`--privileged` no longer have `CAP_SYS_ADMIN`, which is required to mount tmpfs inside the
container. The LHC@home ATLAS wrapper chain needs to mount a tmpfs at `/var/www/lighttpd` to
serve completed simulation results — without this mount, lighttpd cannot start, and completed
simulation output cannot be retrieved.

This is not an AppArmor issue, not a Landlock issue, and not a seccomp issue. The capability
is the problem: the syscall is allowed but `CAP_SYS_ADMIN` is absent.

### The `docker_container_options` Dead End

BOINC's `cc_config.xml` documents a `docker_container_options` directive intended to pass
additional flags to container creation. The obvious fix would be:

```xml
<docker_container_options>--privileged</docker_container_options>
```

**This does not work in BOINC 8.2.8.** The directive is parsed but silently ignored — the
flag is never passed to the docker invocation. This was filed as a bug:

> **BOINC GitHub Issue #6914**
> `docker_container_options` in cc_config.xml silently ignored — no way to pass `--privileged`
> to LHC@home containers (BOINC 8.2.8)
> https://github.com/BOINC/boinc/issues/6914

### Fix: Docker Wrapper Script

Since the BOINC-native solution is broken, the fix intercepts docker at the binary level.

The real docker binary is moved aside and replaced with a wrapper that injects `--privileged`
for `run` and `create` subcommands, then delegates to the real binary:

```bash
#!/bin/bash
# /usr/bin/docker — wrapper script
# Injects --privileged for BOINC/LHC@home compatibility with docker-ce 29.x
# Real binary: /usr/bin/docker.real

REAL_DOCKER=/usr/bin/docker.real

if [[ "$1" == "run" || "$1" == "create" ]]; then
    shift
    exec "$REAL_DOCKER" "${1%run}" run --privileged --user 122:127 "$@"
else
    exec "$REAL_DOCKER" "$@"
fi
```

The wrapper also injects `--user 122:127` (boinc uid:gid) to ensure output files are created
with the correct ownership — see Issue 2.

### Protecting the Wrapper from Package Updates

A docker-ce package update will silently overwrite `/usr/bin/docker` with the real binary,
destroying the wrapper. Use `dpkg-divert` to make this upgrade-proof:

```bash
# Move the real binary and register the diversion
sudo dpkg-divert --divert /usr/bin/docker.real --rename /usr/bin/docker

# Now install the wrapper at /usr/bin/docker
sudo install -m 755 /path/to/wrapper /usr/bin/docker
```

After this, `apt upgrade docker-ce` will install the new docker binary to
`/usr/bin/docker.real` (via the diversion) and leave your wrapper at `/usr/bin/docker`
untouched.

**Verify after any docker-ce upgrade:**
```bash
head -3 /usr/bin/docker   # should show bash shebang and wrapper comment
docker version            # should work (wrapper delegates to real binary)
```

---

## Issue 2 — Output Files Owned as root:root

### Symptom

Tasks run to completion but BOINC cannot move `output.tgz` from the slot directory to the
project directory. The file exists but is owned `root:root`. BOINC, running as the `boinc`
user, lacks permission to move it, causing the task to be reported as failed despite having
completed successfully.

### Root Cause

The Docker container runs processes as root by default. Output files written inside the
container are owned `root:root` on the host filesystem. The `--user 122:127` flag in the
wrapper (boinc uid:gid) addresses this for new containers, but a belt-and-suspenders chown
service provides ongoing coverage.

### Fix: Chown Janitor Service

A systemd service and timer that periodically corrects ownership of files in BOINC slot
directories:

```bash
# /etc/systemd/system/boinc-chown.service
[Unit]
Description=Fix BOINC slot file ownership for LHC@home Docker output

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'find /var/lib/boinc-client/slots -name "output.tgz" -user root -exec chown boinc:boinc {} \;'
```

```bash
# /etc/systemd/system/boinc-chown.timer
[Unit]
Description=Periodically fix BOINC slot file ownership

[Timer]
OnBootSec=1min
OnUnitActiveSec=2min

[Install]
WantedBy=timers.target
```

---

## Issue 3 — boinc User Missing Group Membership

### Symptom

LHC@home tasks fail silently. No obvious error in stderr. Docker appears to function
correctly from the command line as root or as your user account, but BOINC-launched
containers fail.

### Root Cause

The `boinc` user account (which runs the boinc-client service) must be a member of the
`docker` group to invoke docker, and the `vboxusers` group for VirtualBox-based tasks.
A fresh BOINC installation or docker-ce reinstallation may not add the boinc user to
these groups automatically.

### Fix

```bash
sudo usermod -aG docker boinc
sudo usermod -aG vboxusers boinc
```

Restart boinc-client after making group changes — group membership is resolved at process
start and a running daemon will not pick up the change without a restart.

```bash
sudo systemctl restart boinc-client
# or if running manually:
# stop and restart via stop.sh / start.sh
```

**Verify:**
```bash
groups boinc
# should include: boinc docker vboxusers
```

---

## Interaction with BOINC Startup Mode

These workarounds assume boinc-client has access to Docker. If boinc is started manually
via `sudo boinc --redirectio &` (as on pots) rather than via systemctl, confirm that:

- The wrapper at `/usr/bin/docker` is executable by root
- The `boinc-chown.timer` is enabled and active: `systemctl status boinc-chown.timer`

The systemd `Requires=docker.service` dependency in `boinc-client.service.d/docker-dep.conf`
is advisory only when boinc is started manually.

---

## Community Reports

## Community Reports

These issues were reported to the LHC@home community and BOINC project:

| Report | Date | URL |
|---|---|---|
| LHC@home forum: docker-ce 29.x breaks ATLAS tasks — tmpfs mount failure and the fix | 18 Mar 2026 | https://lhcathome.cern.ch/lhcathome/forum_thread.php?id=6468 |
| LHC@home forum: silent task failures — boinc user missing docker and vboxusers group membership | 16 Mar 2026 | https://lhcathome.cern.ch/lhcathome/forum_thread.php?id=6469 |
| LHC@home forum: ATLAS jobs survive BOINC client restart — CVMFS orphan processes and the fix | 16 Mar 2026 | https://lhcathome.cern.ch/lhcathome/forum_thread.php?id=6470 |
| BOINC GitHub Issue #6914: `docker_container_options` silently ignored in BOINC 8.2.8 | 16 Mar 2026 | https://github.com/BOINC/boinc/issues/6914 |
---

## Diagnostic Reference

Check wrapper is in place:
```bash
head -3 /usr/bin/docker
```

Check boinc user groups:
```bash
groups boinc
```

Check chown timer:
```bash
systemctl status boinc-chown.timer
```

Check a failing task's stderr:
```bash
cat /var/lib/boinc-client/slots/<N>/stderr.txt | tail -50
```

Check docker is functional as boinc would invoke it:
```bash
sudo -u boinc docker version
```
