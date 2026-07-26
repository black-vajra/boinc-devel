# LHC concurrency recovery — 2026-07-25

## Incident

BOINC launched three CMS virtual-machine workloads on `pots`. Each CMS task
declared four CPUs and approximately 4.6 GiB of working memory.

Two tasks were recorded as executing. A third was marked suspended by BOINC,
but its `VBoxHeadless` process continued consuming CPU because suspended
applications were being retained in memory.

The result was approximately 17.8 GiB of physical-memory use and three active
VirtualBox workers.

## Affinity-manager behavior

The affinity manager correctly maintained its four-core aggregate ceiling, but
its multiple-worker fallback was inappropriate for LHC workloads.

With three workers and four managed cores, it reduced the preferred two-core
minimum and allocated the workers in a `1 + 2 + 1` arrangement. It then rotated
that arrangement through CPU blocks `0-3`, `4-7`, and `8-11`.

Affinity control limits where existing processes execute. It does not tell the
BOINC scheduler how many project tasks may start. Scheduler concurrency must
therefore be constrained independently.

## Root cause

There was no effective project-wide one-task limit. BOINC simulated 14 CPUs,
used 11 while the computer was active, and could schedule multiple four-CPU CMS
tasks.

The `leave_apps_in_memory` preference also allowed a preempted VirtualBox
workload to remain resident. In this incident, that supposedly suspended VM
continued using CPU.

## Correction

The LHC project configuration now establishes both a project-wide limit and
explicit per-application limits:

```xml
<app_config>
    <project_max_concurrent>1</project_max_concurrent>

    <app>
        <name>ATLAS</name>
        <max_concurrent>1</max_concurrent>
    </app>

    <app>
        <name>CMS</name>
        <max_concurrent>1</max_concurrent>
    </app>

    <app>
        <name>Theory</name>
        <max_concurrent>1</max_concurrent>
    </app>
</app_config>
```

The local preferences override now contains:

```xml
<leave_apps_in_memory>0</leave_apps_in_memory>
```

The client and affinity services were stopped cleanly and restarted so that
stale VirtualBox processes were removed and the new limits took effect.

## Validation

BOINC 8.2.13 explicitly logged:

- `Max 1 concurrent jobs`
- `ATLAS: Max 1 concurrent jobs`
- `CMS: Max 1 concurrent jobs`
- `Theory: Max 1 concurrent jobs`

After restart:

- exactly one CMS task was executing;
- all other CMS tasks were uninitialized or preempted with PID 0;
- exactly one `vboxwrapper` and one `VBoxHeadless` process existed;
- `boinc-client.service` and `boinc-affinity.service` were active;
- `KillMode=control-group` and the two-minute stop timeout remained effective.

## Deployment

Repository reference:

```text
config/kubuntu/lhc-app_config.xml
```

Live Kubuntu location:

```text
/var/lib/boinc-client/projects/lhcathome.cern.ch_lhcathome/app_config.xml
```

## Remaining hardening

The affinity manager should eventually treat multiple simultaneous LHC workers
as a concurrency-policy violation instead of silently reducing per-worker core
allocations. That change requires separate implementation and validation; it
was not made during this recovery.
