# Systemd Configuration

*Applies to: BOINC 8.x, systemd, Linux*

---

## Overview

The BOINC setup on pots uses three systemd units, two of which are drop-ins modifying the
upstream boinc-client package unit. Understanding why each setting exists matters when
troubleshooting or adapting this configuration to other systems.

---

## boinc-client.service.d/docker-dep.conf

Location: `/etc/systemd/system/boinc-client.service.d/docker-dep.conf`

This drop-in adds Docker as a hard dependency for boinc-client and corrects the process
termination behaviour on shutdown.

    [Unit]
    After=docker.service
    Requires=docker.service

    [Service]
    TimeoutStopSec=120
    KillMode=control-group

### After=docker.service

Ensures boinc-client does not start until Docker is fully up. LHC@home ATLAS tasks launch
Docker containers immediately on startup. If boinc-client starts before Docker is ready,
the first task invocations fail and BOINC records computation errors before Docker has had
a chance to initialise.

### Requires=docker.service

Makes Docker a hard dependency. If Docker fails or is stopped, boinc-client will also be
stopped. Without this, boinc-client could run in a state where Docker is unavailable and
every LHC task silently fails.

Note: both of these directives are advisory only when BOINC is started manually via
start.sh rather than via systemctl. The dependency chain is only enforced when systemd
manages the startup.

### TimeoutStopSec=120

The default systemd stop timeout is 90 seconds, after which systemd sends SIGKILL. With
LHC@home ATLAS tasks running long Docker container chains and CVMFS mounts, 90 seconds is
insufficient for a clean shutdown. BOINC needs time to checkpoint active tasks, flush
client_state.xml to disk, and wait for any in-flight Docker operations to complete.

If BOINC is killed mid-write of client_state.xml, the file is corrupted and attached
projects may disappear from the project list on next startup, requiring manual re-attachment
via boinccmd --project_attach.

120 seconds gives BOINC adequate time for a clean shutdown in normal circumstances.

### KillMode=control-group

This setting determines what systemd kills when stopping boinc-client.

KillMode=process (the default, and what was used initially) sends the stop signal only to
the main boinc process. Any child processes — including Docker containers and CVMFS-hosted
ATLAS workers — are left running. This is inadequate: stopped tasks accumulate, and on the
next start BOINC may find stale processes competing for resources.

KillMode=control-group sends the stop signal to every process in boinc-client's cgroup —
the main process and all its descendants. This correctly cleans up Docker containers and
worker processes that are still attached to the cgroup at stop time.

The important caveat: processes that have already escaped the cgroup via CVMFS re-parenting
(ATLAS orphans, re-parented to PID 1) are not in boinc-client's cgroup and are not affected
by this setting. See ATLAS_ORPHAN_PROBLEM.md for how those are handled separately.

---

## boinc-affinity.service

Location: `/etc/systemd/system/boinc-affinity.service`

    [Unit]
    Description=BOINC CPU Affinity Manager
    After=boinc-client.service

    [Service]
    Type=simple
    ExecStartPre=/bin/sleep 5
    ExecStart=/usr/local/bin/boinc_affinity.sh
    Restart=always
    RestartSec=15
    AmbientCapabilities=CAP_SYS_NICE
    CapabilityBoundingSet=CAP_SYS_NICE
    StandardOutput=journal
    StandardError=journal
    SyslogIdentifier=boinc-affinity

    [Install]
    WantedBy=multi-user.target

### After=boinc-client.service

Start ordering only — the affinity service starts after boinc-client but is not bound to
its lifecycle. This is intentional. See the BindsTo section below.

### ExecStartPre=/bin/sleep 5

Gives boinc-client time to spawn its initial worker processes before the affinity script
begins scanning. Without this delay, the script's first cycle finds no workers and logs
a waiting message before boinc has finished starting up. Five seconds is conservative
but reliable.

### Restart=always

The script is designed to run continuously as a daemon. Restart=always ensures it is
restarted regardless of how it exits — including clean exits (exit code 0) triggered by
SIGTERM. This matters because systemd sends SIGTERM to the script whenever boinc-client
restarts for a scheduler cycle, which would cause Restart=on-failure to silently not
restart it.

### RestartSec=15

Fifteen second cooldown between restarts. Prevents a tight restart loop if the script
is failing immediately on startup (e.g. a syntax error after editing).

### AmbientCapabilities=CAP_SYS_NICE

The script calls taskset and renice on processes owned by other users, including
root-owned ATLAS orphan processes. CAP_SYS_NICE is required to adjust the scheduling
priority and CPU affinity of processes not owned by the calling user. Without this
capability, taskset and renice silently fail on foreign-owned processes.

AmbientCapabilities makes the capability available to the script process itself (not just
to setuid binaries it might invoke).

### CapabilityBoundingSet=CAP_SYS_NICE

Limits the service to only CAP_SYS_NICE — it cannot acquire any other elevated capability
regardless of what binaries it invokes. Principle of least privilege.

### SyslogIdentifier=boinc-affinity

Tags all journal entries from this service with the identifier boinc-affinity, making
log filtering clean:

    journalctl -u boinc-affinity -f

---

## boinc-affinity.service — Historical Note: BindsTo

An earlier version of the unit included:

    BindsTo=boinc-client.service

The intent was to stop the affinity service automatically when boinc-client stopped.
This caused a problem: boinc-client restarts itself periodically for scheduler RPC cycles.
Each restart triggered a SIGTERM to the affinity service (clean exit), which Restart=on-failure
did not catch, leaving the affinity service dead until manually restarted.

The fix was to clear BindsTo with an empty assignment in a drop-in:

    BindsTo=

An empty assignment explicitly clears the directive inherited from the main unit file. This
is a general systemd pattern for removing inherited directives in drop-ins — it is not
sufficient to simply omit the directive, as omission leaves the inherited value in place.

The BindsTo= clearing was later merged directly into the main unit file, removing the need
for a separate drop-in. The affinity service now manages its own lifecycle independently
via Restart=always.

---

## boinc-chown.service and boinc-chown.timer

Location: `/etc/systemd/system/boinc-chown.service` and `boinc-chown.timer`

A oneshot service and accompanying timer that periodically corrects ownership of LHC@home
output files from root:root to boinc:boinc. Required because Docker containers running as
root write output files that the boinc user cannot move. See LHC_DOCKER_COMPATIBILITY.md
for full context.

The timer runs every 2 minutes. The service performs a targeted find across BOINC slot
directories, chowning only files currently owned by root. On a system with no active
LHC tasks the operation is near-instantaneous.

---

## General Notes for Administrators

Drop-in files override only the directives they contain. Any directive not present in a
drop-in inherits its value from the main unit file. To explicitly clear an inherited
directive, assign it an empty value in the drop-in.

The order of drop-in application is alphabetical by filename. If you have multiple drop-ins
that set the same directive, the last one alphabetically wins.

After editing any unit file or drop-in, reload the systemd daemon before restarting the
service:

    sudo systemctl daemon-reload
    sudo systemctl restart <service>

Without daemon-reload, systemd continues using the cached version of the unit and your
changes have no effect.
