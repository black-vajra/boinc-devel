 Proposal: Zero-Config Volunteer Computing for LHC@home
 Reducing Volunteer Attrition Through Robust Task Execution Infrastructure

Author: superkali (github.com/black-vajra)
Date: April 2026
Related issues: BOINC 6931, BOINC 6957
Repository: github.com/black-vajra/boinc-devel

---

 Executive Summary

LHC@home's current task execution architecture — spanning both VirtualBox-based ATLAS tasks and Docker-based Theory Simulation tasks — imposes a configuration burden on volunteers that is incompatible with broad participation. The result is silent volunteer attrition at scale: most volunteers who hit these issues never report them. They simply stop contributing.

This proposal documents the specific failure modes encountered on a modern, well-configured Linux desktop, proposes concrete architectural improvements, and makes the case that the four-year Long Shutdown 3 (LS3) window — beginning July 2026 — represents an ideal and possibly irreplaceable opportunity to address these issues before the High-Luminosity LHC (HL-LHC) era begins in 2030 with ten times the simulation demand.

---

 1. The Volunteer Attrition Problem

BOINC's value proposition to science projects is straightforward: tap into millions of volunteer computers worldwide with minimal friction. Einstein@Home and MilkyWay@home demonstrate this working correctly — a volunteer installs BOINC, adds the project, and tasks run. No additional configuration required. These projects work on essentially any modern Linux, Windows, or Mac system without modification.

LHC@home does not work this way.

Both of its primary compute workloads — ATLAS (VirtualBox) and Theory Simulation (Docker) — require significant post-installation configuration that is not documented in any single place, not enforced by the software itself, and not recoverable without expert knowledge when it fails. The community-maintained "Yeti Checklist" for ATLAS — a multi-page troubleshooting document that has been through three major versions — is the clearest possible signal that the onboarding experience is broken. When volunteers need a community-written survival guide to run your software, the software has a usability problem.

The volunteers who succeed with LHC@home are not representative of the volunteer pool. They are experienced Linux administrators, Windows power users who understand virtualization, and people willing to spend days debugging. This is a small fraction of BOINC's potential volunteer base.

The volunteers who fail with LHC@home are invisible. They do not post to forums. They do not file bug reports. They simply detach from the project and contribute their compute elsewhere, or stop contributing entirely. The forum record shows only those who persist long enough to ask for help — the tip of the iceberg.

---

 2. Documented Failure Modes

The following failure modes are documented from first-hand experience on a modern system: Kubuntu 24.04, BOINC 8.2.9, Intel Core Ultra 5 245K (14 cores), 30.8 GiB RAM, AMD GPU, docker-ce 29.x. This is not a marginal or poorly-configured system. It represents current mainstream Linux hardware.

All configuration steps, debugging sessions, and workarounds are documented in full at github.com/black-vajra/boinc-devel, including the complete timeline from initial BOINC installation through each failure and its resolution.

 2.1 Docker-Based Tasks (Theory Simulation)

 2.1.1 docker-ce 29.x Compatibility Failure (BOINC issue 6931)

When docker-ce 29.x is installed — the current stable release for Debian/Ubuntu systems — Theory Simulation tasks fail silently with "computation error." The root cause is that Docker 29 introduced stricter default security profiles, and LHC@home's containers require `CAP_SYS_ADMIN` to mount tmpfs inside the container for lighttpd's working directory. Without this capability, lighttpd cannot start, completed simulations cannot serve their results, and all output is lost.

The failure mode is entirely silent from the volunteer's perspective: tasks run, appear to complete, then report "computation error." No actionable error message is surfaced. The volunteer has no indication that the problem is a Docker version incompatibility rather than a hardware or configuration issue.

The workaround required: A dpkg-divert-protected wrapper script replacing `/usr/bin/docker` that intercepts every container creation and injects `--privileged`. Additionally, a separate systemd service that periodically corrects output file ownership from `root:root` back to `boinc:boinc` so BOINC can move completed output to the upload queue.

These are not things a typical volunteer can discover, implement, or maintain. The `--privileged` injection requires understanding Docker security models, dpkg-divert, and systemd. The ownership correction service requires understanding BOINC's internal file management.

The correct fix: LHC@home's container definitions should either specify the required capabilities explicitly, or the docker_wrapper should be updated to pass `--cap-add=SYS_ADMIN` (or `--privileged` where necessary) when creating containers. This should be handled at the project level, transparently, without volunteer intervention.

 2.1.2 docker_wrapper_18 Infinite Loop on Container Exit (BOINC issue 6957)

When a Theory Simulation container finishes its computation and exits, docker_wrapper_18 fails to detect the exit condition. Rather than proceeding to output collection, the wrapper enters an infinite loop issuing pause/unpause commands against the dead container:

```
running docker command: pause boinc__lhcathome.cern.ch_lhcathome__theory_2922-XXXXXXX
Error response from daemon: container ... is not running
running docker command: unpause boinc__lhcathome.cern.ch_lhcathome__theory_2922-XXXXXXX
Error response from daemon: Container ... is not paused
```

This loop continues indefinitely. Tasks display 100% progress and "Running" status in BOINC Manager but never transition to upload state. This was confirmed running for 12+ hours without resolution. The wrapper has no timeout, no exit condition, and no error handler for the "container not running" response.

From the volunteer's perspective: tasks appear to be running normally at 100% completion. There is no indication anything is wrong. The volunteer may leave the machine running overnight expecting results in the morning, and find the same tasks still "running" at 100% with no uploads.

The workaround: Manually identifying and killing the wrapper process for each stuck task, which causes BOINC to report "Computation for task X finished" and clean up correctly. This must be done per-task, requires command-line access, and must be repeated for every future occurrence.

The correct fix: docker_wrapper must handle container exit detection robustly, with a timeout fallback. "Container not running" is a terminal condition that should trigger output collection, not an infinite retry loop.

 2.1.3 max_concurrent Enforcement Failure

`app_config.xml` with `<max_concurrent>1</max_concurrent>` for Docker tasks is completely ignored by BOINC 8.2.9. Tasks download and execute 9-10 simultaneously regardless of this setting. `<project_max_concurrent>1</project_max_concurrent>` is also ignored. Both settings were confirmed active via `boinccmd --get_app_config` — BOINC acknowledges the configuration but does not enforce it.

The consequence: with 10 containers competing for scheduler time, BOINC's pause/unpause cycle prevents any single container from receiving enough uninterrupted time to complete the lighttpd output handshake. This directly compounds the container exit detection bug above, creating a failure cascade where tasks that might have completed individually become permanently stuck in a thrashing loop.

On a 30.8 GiB system, 10 concurrent Docker tasks also consume memory beyond the available headroom, pushing the system into swap and degrading performance for all workloads.

The correct fix: `max_concurrent` must be enforced for Docker tasks. The current default behavior — unlimited concurrent Docker tasks — is the worst possible default for volunteer hardware. A sensible default would be 1 concurrent Docker task, adjustable upward by volunteers with appropriate hardware.

 2.1.4 Containers Stuck in Created State

Some containers never progress past Docker's "Created" status and are never started by the wrapper. Tasks remain permanently stuck with 0% CPU activity and no progress. This appears to be a wrapper state machine failure — the wrapper creates the container but never issues the start command under certain scheduling conditions.

---

 2.2 VirtualBox-Based Tasks (ATLAS)

The ATLAS task failure modes are distinct from the Docker failures but share the same root characteristic: they require expert intervention that typical volunteers cannot provide.

 2.2.1 CVMFS Process Orphaning

ATLAS tasks run through CVMFS (`/cvmfs/atlas.cern.ch/...`). At some point in the execution chain, the primary worker process (`python runargs.EVNTtoHITS.py`) is re-parented to PID 1 (init), completely escaping the BOINC process tree. This has several consequences:

- BOINC cannot account for the process's CPU usage
- BOINC cannot kill the process on task abort or client restart
- The orphaned process continues consuming 200-300% CPU indefinitely after BOINC has moved on
- On a volunteer machine, one core remains permanently pegged at 100% even with BOINC stopped — invisible to the volunteer unless they examine running processes

The volunteer experience: BOINC appears to be idle or stopped, but the machine remains hot, fans remain loud, and one core remains fully loaded. The volunteer may believe their machine is infected with malware, or that BOINC is misbehaving, and uninstall entirely.

The workaround required: A custom process detection script that searches for ATLAS-specific process names system-wide, bypassing the BOINC process tree entirely. Plus startup cleanup routines that kill known orphan process signatures before launching BOINC. This is sophisticated systems programming that no typical volunteer would implement.

The correct fix: ATLAS task execution should not allow worker processes to escape the BOINC-managed process group. If CVMFS re-parenting is unavoidable, BOINC should be informed of the relevant PIDs so it can track and manage them.

 2.2.2 Configuration Complexity

The community-maintained ATLAS checklist — recommended by LHC@home project staff — lists the following prerequisites for running ATLAS tasks successfully:

- Specific VirtualBox version requirements (with noted incompatibilities across versions)
- BIOS virtualization extensions enabled (VT-x/AMD-V) — with guidance on how to check and enable
- VirtualBox Extension Pack installation
- Firewall rules for 5 specific ports (80, 443, 3128, 5222, 9094)
- Antivirus exclusions for the BOINC data directory
- Memory allocation tuning (3.9+ GB per ATLAS WU, with complex multi-core scaling formulas)
- Manual `app_config.xml` configuration to limit concurrent tasks
- Conflict warnings about Docker and Hyper-V interfering with VirtualBox
- Multiple troubleshooting scenarios (A through E) covering common failure modes

This checklist is the documentation. It is community-maintained, last formally updated in 2017, and represents years of accumulated volunteer debugging effort. Its existence is an indictment of the installation experience, not a solution to it.

A volunteer who installs BOINC, adds LHC@home, and simply runs it will encounter a subset of these issues silently. They will not know to consult the checklist. They will see computation errors and assume the project doesn't work on their hardware.

---

 3. The LS3 Opportunity

Long Shutdown 3 begins in July 2026 and runs for approximately 47 months, with HL-LHC first beam targeted for June 2030. During this period:

- The LHC itself will not be producing collision data
- ATLAS and CMS detectors will undergo major upgrades
- Simulation workload will continue and likely increase as teams prepare theoretical predictions for HL-LHC physics
- The LHC@home volunteer infrastructure will continue operating without the pressure of real-time data production

This is the optimal window to address volunteer infrastructure problems. There is no competing pressure from live physics runs. The development team has time to redesign, test, and deploy fixes without risking disruption to active data-taking periods.

When HL-LHC Run 4 begins in 2030, it will produce collision data at 10x the current luminosity. The simulation demand will scale accordingly. If volunteer infrastructure is not improved before Run 4, LHC@home will face that expanded simulation demand with the same broken onboarding experience and the same silent volunteer attrition.

The window to fix this is now. Four years is exactly enough time to do it properly.

---

 4. Proposed Architectural Improvements

 4.1 Immediate Fixes (Addressable in Weeks)

4.1.1 docker_wrapper exit detection (BOINC issue 6957)
Add a handler for the "container not running" error response from pause/unpause commands. This is a missing conditional branch in the wrapper's main loop. When the container is confirmed not running, proceed to output collection rather than retrying indefinitely.

4.1.2 max_concurrent enforcement for Docker tasks
The BOINC client's failure to enforce `app_config.xml` for Docker tasks is a scheduler bug. Until fixed upstream, LHC@home should set a server-side default that limits concurrent Docker tasks per host. The current behavior — unlimited concurrency — guarantees resource exhaustion on volunteer hardware.

4.1.3 docker-ce 29.x compatibility
The `--privileged` (or appropriate `--cap-add`) flag should be specified in the container definition or passed by docker_wrapper at container creation time. This should not require volunteer-side workarounds.

 4.2 Short-Term Improvements (Addressable in Months)

4.2.1 Actionable error surfacing
When a task fails due to a known configuration issue (wrong Docker version, missing capabilities, VirtualBox not installed, insufficient memory), the error message presented to the volunteer should identify the specific cause and link to a remediation guide. "Computation error" tells the volunteer nothing.

4.2.2 Resource guardrails by default
Docker tasks should enforce memory limits at the container level, independent of BOINC's preference system. A task that requires 3.9 GB should fail immediately and gracefully if that memory is unavailable, rather than starting successfully and OOM-killing mid-execution.

4.2.3 CVMFS process tracking for ATLAS
If ATLAS worker processes must escape the BOINC process tree via CVMFS re-parenting, the wrapper should communicate the escaped PIDs back to the BOINC client so they can be tracked, resource-limited, and killed on task abort.

4.2.4 Consolidated, maintained documentation
The ATLAS checklist is community-maintained and 7+ years old. LHC@home should maintain official, versioned setup documentation that is updated when software versions change. This documentation should be surfaced directly in BOINC Manager when a volunteer first adds the project.

 4.3 Architectural Goals (Addressable Over LS3)

4.3.1 Zero-config target for Docker tasks
The Docker-based task execution path should work correctly on any system where Docker is installed and BOINC can communicate with the Docker daemon. No volunteer-side configuration — no wrapper scripts, no capability adjustments, no ownership correction services — should be required. If the project requires `--privileged`, that should be specified in the task definition and passed transparently.

4.3.2 Graceful degradation over silent failure
When a volunteer's system cannot run a particular task type — wrong Docker version, insufficient memory, missing VirtualBox — the BOINC client should detect this before downloading work, report the specific incompatibility, and either request compatible work or clearly communicate to the volunteer what upgrade is needed.

4.3.3 Volunteer hardware diversity as a design constraint
LHC@home's architecture should be tested against the full range of volunteer hardware, not just the systems of developers and experienced administrators. A volunteer running a stock Ubuntu or Windows installation with default settings should be a first-class target, not an edge case.

---

 5. The Broader Case

The volunteers who contribute to LHC@home are motivated by genuine interest in particle physics and a desire to contribute to real science. That motivation is renewable — there is no shortage of people who would run ATLAS simulations on their home computers if the experience were not actively hostile to non-experts.

Einstein@Home has demonstrated that BOINC volunteer computing can scale to hundreds of thousands of participants on diverse hardware with minimal support burden. The difference is not the science — it is the execution infrastructure. Native binaries with no external dependencies simply work.

LHC@home's use of VirtualBox and Docker is scientifically justified — the software environments required for ATLAS and Theory simulations are complex and cannot easily be compiled as portable native binaries. But the virtualization layer should be transparent to volunteers, not a source of failure modes that require expert intervention.

The goal is not to make LHC@home as simple as Einstein@Home — the scientific requirements are fundamentally different. The goal is to make LHC@home work correctly for a volunteer who installs BOINC, adds the project, and runs it without reading any documentation. That volunteer should complete tasks successfully, receive credits, and have no reason to detach from the project.

Every volunteer who churns off LHC@home due to configuration failures is compute that CERN doesn't get. With HL-LHC Run 4 requiring ten times the simulation capacity, that gap matters.

---

 6. Supporting Materials

- Full configuration history and debugging logs: github.com/black-vajra/boinc-devel
- Task lifecycle capture showing stuck tasks: docs/completion_watch.log in above repository
- BOINC issue 6931: docker_container_options feature request (same volunteer, same machine)
- BOINC issue 6957: docker_wrapper exit detection and max_concurrent enforcement
- LHC@home forum thread: docker-ce 29.x compatibility (Theory Simulation board)
- Community ATLAS checklist (v3, last updated 2017): referenced in LHC@home FAQ

---

This proposal is submitted in the spirit of constructive contribution to a project whose science goals are worth the engineering investment required to realize its volunteer computing potential.
