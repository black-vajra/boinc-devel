# BOINC state and service recovery — 2026-07-25

## Symptom

Starting the service-managed client unexpectedly restored Einstein@Home and
MilkyWay@home beside LHC@home. The affinity service also appeared abnormal, and
BOINC Manager temporarily showed an empty, disconnected view.

## Root cause

Two independent BOINC data trees had diverged:

- `/home/pepper`: historical root-run client, LHC@home only.
- `/var/lib/boinc-client`: systemd client, stale Einstein, LHC, and MilkyWay
  attachments.

No account manager reattached the projects. Different launch paths selected
different `client_state.xml` files. Manual start/stop scripts also allowed a
second root client and broad process killing.

## Recovery

The user designated the newest LHC-only state and newest affinity script as
authoritative. The LHC-only state was staged, validated, ownership-corrected,
and atomically promoted to `/var/lib/boinc-client`. The old service tree was
retained under a timestamped `before-lhc-authority` path for rollback.

A stale root helper that repeatedly changed slot ownership was stopped.
`boinc-client.service` now owns its full process tree with:

```ini
KillMode=control-group
TimeoutStopSec=2min
```

The deployed affinity manager was synchronized with the repository version. It
limits active BOINC work to four CPUs and rotates exact blocks across CPUs
`0-11`, leaving `12-13` reserved.

## Validation

- BOINC 8.2.13 active from `/var/lib/boinc-client`
- only LHC@home attached
- client and affinity services active
- RPC listening on `127.0.0.1:31416`
- ATLAS worker observed rotating `0-3`, `4-7`, `8-11`
- BOINC Manager reconnected after closing the stale GUI and relaunching it from
  the authoritative data-directory context

## Rule going forward

Run exactly one client, under systemd, with `/var/lib/boinc-client` as the sole
Kubuntu state directory. Do not launch BOINC as root from `/home/pepper`.
