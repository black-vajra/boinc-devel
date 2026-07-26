# Canonical SableLinux ATLAS Startup Validation — 2026-07-26

## Host

Canonical Z890 SableLinux system.

Kernel:

`6.16.1-sable-lhc-test1`

BOINC:

`8.2.11`

CVMFS:

`2.13.3`

## Result

The canonical host successfully started an LHC@home ATLAS native
multithreaded workload.

Validated execution chain:

BOINC → LHC@home → CVMFS → Apptainer → ATLAS Pilot 3

## BOINC policy

- Service account: `boinc`
- Data directory: `/var/lib/boinc-client`
- Service disabled at boot
- Service manually started for validation
- Only LHC@home attached
- Any compatible LHC@home application allowed
- Beta work allowed
- CPU and AMD GPU work allowed
- Maximum one concurrent LHC@home job

## CVMFS validation

The `boinc` account successfully accessed:

- `cvmfs-config.cern.ch`
- `atlas.cern.ch`
- `atlas-condb.cern.ch`
- `grid.cern.ch`
- `unpacked.cern.ch`

The ATLAS wrapper independently confirmed the ATLAS repositories during task
startup.

## Container validation

The ATLAS wrapper did not require a host-installed Apptainer binary.

It successfully used the Apptainer runtime supplied from:

`/cvmfs/atlas.cern.ch`

The container started successfully and launched ATLAS Pilot 3.

## Workload

- BOINC task: `3fb2477951fe_0`
- ATLAS Panda ID: `7234891001`
- Application path: `native_mt`
- CPU threads: 7
- Slot: `/var/lib/boinc-client/slots/0`

## Acceptance state

Validated:

- Scheduler communication
- Work download
- CVMFS access
- Container startup
- ATLAS pilot startup
- BOINC progress reporting
- One-job concurrency

Still pending:

- Athena sustained execution
- Expected output creation
- Successful task completion
- Successful result upload
- Scheduler validation

This is a startup milestone, not yet a completed-workload certification.

## Authority

The detailed evidence and canonical operating record are maintained in the
SableLinux repository. This document is the BOINC/LHC subproject summary.
