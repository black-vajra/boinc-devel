# Canonical Z890 Native ATLAS CVMFS Prerequisite Validation

Date: 2026-07-26
Canonical host: Z890 SableLinux
BOINC version: 8.2.11
BOINC installation: /opt/boinc/8.2.11
BOINC data directory: /var/lib/boinc-client
Kernel: 6.16.1-sable-lhc-test1

## Objective

Validate the native LHC@home ATLAS execution path on the canonical Z890 through initial work acquisition, wrapper launch, runtime prerequisite checking, controlled failure reporting, and work-fetch suspension.

## Configuration

The LHC@home project was attached successfully.

The project configuration contained:

    <app_config>
        <project_max_concurrent>1</project_max_concurrent>
    </app_config>

BOINC detected the configuration:

    [LHC@home] Found app_config.xml

The setting limits the number of concurrently executing project tasks. It does not limit the number of CPU threads assigned to a multithreaded ATLAS task.

The project supplied one ATLAS task requesting seven CPU threads:

    name: ffa5a650cfd1_0
    resources: 7 CPUs

## Validated Results

The following stages passed:

1. BOINC client startup.
2. GUI RPC authentication.
3. LHC@home project attachment.
4. Scheduler communication.
5. Work-unit acquisition.
6. Application and input-file downloads.
7. Large ATLAS event input download.
8. app_config.xml discovery.
9. Single-task concurrency enforcement.
10. BOINC slot creation.
11. Wrapper execution.
12. Native ATLAS launcher execution.
13. Seven-thread argument propagation.
14. Controlled task failure reporting.
15. Scheduler acceptance of the failed result.
16. No-new-work control.

Observed execution:

    wrapper_26015_x86_64-pc-linux-gnu --nthreads 7
    /bin/bash run_atlas --nthreads 7

## Runtime Failure

The ATLAS native launcher checked for CernVM-FS and failed before scientific execution:

    Checking for CVMFS
    No cvmfs_config command found
    Failed to list /cvmfs/atlas.cern.ch/repo/sw
    It looks like CVMFS is not installed.
    CVMFS is required to run ATLAS native tasks.

The wrapper entered its intentional 600-second cleanup delay and exited without producing:

    shared/result.tar.gz
    shared/HITS.pool.root.1

BOINC then reported:

    Computation for task ffa5a650cfd1_0 finished
    Output file ffa5a650cfd1_0_r2039021533_ATLAS_result absent
    Reporting 1 completed tasks
    Scheduler request completed

This was an expected controlled failure caused by the missing CVMFS runtime prerequisite.

## Current State

The project remains attached.

Work fetching is suspended:

    [LHC@home] work fetch suspended by user
    [LHC@home] Not requesting tasks: "no new tasks" requested via Manager

There are no active tasks or file transfers.

## Engineering Conclusion

The canonical Z890 BOINC/LHC pipeline is validated through native ATLAS wrapper startup.

The first missing execution dependency is CVMFS. There is no evidence that multiple concurrent tasks, Docker, Podman, Apptainer, or a virtual-machine runtime are required for this specific native ATLAS work unit.

The next isolated phase is:

Add and validate CVMFS on the canonical Z890.

Work fetching must remain suspended until CVMFS is independently installed and validated.

Minimum required validation targets:

    cvmfs_config chksetup
    cvmfs_config probe
    sudo -u boinc ls /cvmfs/atlas.cern.ch/repo/sw
    sudo -u boinc ls /cvmfs/atlas-condb.cern.ch

Only after those checks pass should LHC@home work fetching be resumed.
