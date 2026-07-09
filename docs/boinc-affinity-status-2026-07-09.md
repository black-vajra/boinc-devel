# BOINC affinity status — 2026-07-09

## Current state

The BOINC affinity manager has been updated and tested locally on host `pots`.

Confirmed adjustments:

- Fixed circular CPU affinity wraparound.
  - Previous behavior could shrink near the top of the CPU range, e.g. `8-13`, `10-13`, `12-13`.
  - Corrected behavior now wraps properly, e.g. `9,10,0,1,2,3,4`.

- Added `MAX_MANAGED_CORES=11`.
  - Host has 14 logical cores.
  - BOINC-managed workers are rotated across cores `0-10`.
  - Logical cores `11-13` are left outside the BOINC affinity pool for desktop/system responsiveness.

- Changed `taskset` invocation from `taskset -cp` to `taskset -acp`.
  - This applies affinity to all threads/tasks for a PID.
  - This is intended to improve handling of multithreaded ATLAS native workers.

## Workloads observed

Tested/observed locally:

- Einstein@Home GPU task running alongside CPU helper load.
- LHC@home ATLAS native multithreaded task running and rotating across managed cores.
- LHC@home CMS VirtualBox tasks previously observed running successfully.
- LHC@home Theory Docker tasks are queued/waiting and still need direct validation.

## Pending validation

Next test:

- Temporarily suspend Einstein@Home and non-Theory LHC tasks.
- Allow LHC@home Theory Docker work to run by itself.
- Confirm whether the affinity manager detects and manages the relevant Theory/Docker worker process.
- Confirm task progress, CPU placement, and absence of Docker/BOINC errors.


## Theory validation update

Theory Docker validation was performed after temporarily suspending Einstein@Home and non-Theory LHC@home tasks.

Observed result:

- LHC@home Theory Simulation 302.10 Docker tasks started and entered running state.
- Einstein@Home was successfully suspended during the test.
- CMS was successfully suspended during the test.
- The affinity manager continued assigning active compute workers inside the managed `0-10` CPU pool.
- GPU usage dropped after Einstein suspension, as expected.
- Theory Docker workload is now confirmed to start successfully under this BOINC configuration.

