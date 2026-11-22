# LHC-only affinity — 2026-11-22

## Reason and observed host

User report from pots, 2026-11-22 08:51 EST. The deployed script matches
b345f09 (SHA-256 929ab390a1bad30d4c4d62bcd41f020952c4141c444abba3b2ef3975a9281741).
Einstein has three executing one-CPU tasks, MilkyWay one executing 11-CPU task,
and CMS is SUSPENDED with a retained PID. The old manager selected these
unrelated workers and a VBoxHeadless process and assigned each a one-CPU mask.
The suspended CMS record does not establish current VM CPU consumption because
ps reports lifetime-average CPU use. The watcher source was absent from the
inspection report. Its two units and timer were present, so this change supplies
a replacement watcher explicitly based on executing task records.

## Behavior

The Bash entry point invokes a Python standard-library helper. Both the systemd
ExecCondition and direct script entry require a live BOINC RPC task marked
EXECUTING, scheduled, downloaded, with an LHC project URL and a live PID.
Queued and suspended tasks cannot activate the manager. RPC failure stops the
manager and is logged. The current task roots, descendants, and exact task slot
working directories identify processes. Slot matching also checks the root UID.
Exact BOINC container names identify Docker payload roots via docker inspect.
There is no global process-name match. Cgroup configuration is unchanged.

All identified LHC threads share the four-CPU window, rotating every ten seconds
by four through fourteen allowed CPU IDs. This handles native tasks spawning
multiple science processes while maintaining an aggregate four-CPU window.
The old proportional per-process allocator and lifetime CPU threshold are removed
because only LHC is managed and the intended operation is one LHC task at a time.
CPU IDs come from the service's actual permitted set, supporting noncontiguous
IDs. Existing per-thread masks are retained for cleanup and surviving managed
threads are restored on suspension, exit, RPC failure, or SIGTERM. Kernel start
times distinguish reused PID/TID numbers. No scheduling priority changes are made.

The timer starts with boinc-client.service through WantedBy=boinc-client.service,
and PartOf stops it with BOINC. Requisite prevents manually starting the timer or
manager from starting BOINC itself. The short watcher checks every ten seconds
while BOINC runs, including other-project sessions, and exits after each check.
The affinity manager is inactive whenever no LHC task is executing. Restart=no
prevents restart loops. The timer provides retry after a transient failure.
The manager and watcher use PartOf for BOINC shutdown. They do not start Docker.

## Deployment and migration

Installer is prepared for pots and requires the inspected production/repository
script hash, a clean repository, no newly introduced affinity/watch overrides,
Python 3, and ShellCheck. It backs up production and repository files before
editing either. The production service has no Restart setting, superseding the
older repository's Restart=always policy. Only the affinity scripts and units,
startup integration, regression test, and this report change. BOINC client,
project preferences, one-LHC-job limit, science processes and checkpoints are
not restarted or modified by the installer.

The previous manager never recorded original masks. The one-time reset restores
all confirmed existing BOINC task trees (including retained suspended tasks) to
the BOINC client MainPID's CPU mask, before starting the new manager. This assumes
there were no deliberate task-specific affinity settings apart from the old
manager. Other-process affinity is untouched. Previously applied nice values
remain as the old manager left them. Already orphaned processes whose ancestry,
slot working directory, and Docker container identity are all lost cannot be
safely associated with a current task and are excluded.

Run the included install.sh as pepper with ~/boinc-devel as its argument.
It prints the timestamped backup path and exact rollback command. No Git commit
is made before Pots runtime validation. The rollback restores old production
files and prior enable/active states. New repository files remain for review.

## Validation

Execution host is a scratch Linux container, Python 3.12.14, with no BOINC client
or LHC projects. Thirteen focused regression tests cover suspended CMS with running
Einstein, exact URL filtering, ancestry, queued tasks, malformed RPC output, exact
Docker naming, wraparound/equal coverage, immediate idle exit, PID reuse, actual
OS thread masks with rotation/cleanup, watcher stop behavior on idle/error, per-thread mask restoration, and late-child
mask inheritance.
ShellCheck passes for the installer, rollback, entry point, and watcher. Unit
syntax and dependency verification passes in an isolated systemd root with a
stub BOINC service. No live systemd integration was exercised.

A live two-thread Python subprocess was pinned and rotated, then restored, while
a separate two-thread subprocess retained its original affinity. These tests do
not execute real BOINC science, VirtualBox, or Docker workloads.

Pending on pots: execute tests and ShellCheck, install and verify inactive manager
while CMS is suspended and other projects run. Confirm existing other-project
thread masks match the BOINC client's allowed CPUs after migration. Start LHC
alone through the usual UI and observe at least a full rotation, task progress,
RAM/swap, temperatures and desktop behavior. Suspend LHC and confirm the manager
exits by the next polling pass. Stop BOINC via its usual procedure and confirm
manager, watcher and timer are inactive. Recheck the next BOINC start activates
the timer. Commit only after successful host verification.

## Pots runtime validation — 2026-11-22

PASS: With only Einstein and MilkyWay executing, boinc-affinity.service
was inactive/dead. All inspected MilkyWay threads had affinity 0-13,
matching the BOINC client's allowed CPUs.

PASS: Suspending Einstein and MilkyWay and resuming LHC activated the
manager automatically without restarting BOINC.

PASS: From 10:04:03 through 10:05:03 EST, the manager reported one LHC
task, three processes, and 43-45 threads across all seven four-CPU
rotation positions, including wraparound.

PASS (user-confirmed): The manager exits after suspending LHC.
PASS (user-confirmed): The timer and manager stop automatically when BOINC stops.
