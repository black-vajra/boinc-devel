# boinc-devel

BOINC engineering, operations, recovery notes, and validated configuration for
the `pots` Z890 workstation and related SableLinux validation hosts.

## Current runtime profiles

| Platform | BOINC | Program path | Data path | Control model | Current scope |
|---|---:|---|---|---|---|
| Kubuntu on `pots` | 8.2.13 | `/usr/local/bin` | `/var/lib/boinc-client` | systemd services | LHC@home only; ATLAS/CMS; four-core affinity rotation |
| SableLinux on `pots` | 8.2.11 | `/opt/boinc/current` | `/var/lib/boinc-client` | manual `boincctl`; disabled at boot | Client/GPU validated; LHC rootless-container integration in progress |
| SableLinux EliteBook | 8.2.11 | `/opt/boinc/current` | `/var/lib/boinc-client` | validation host | Source build, Manager, Asteroids, and MilkyWay validation |

The Kubuntu and SableLinux installations share hardware but are distinct
operating-system roots. They must not share live BOINC state directories.

## Repository authority

- `boinc-devel/main` is the synchronized, platform-neutral record of validated
  BOINC work, reusable scripts, operational procedures, and incident summaries.
- SableLinux integration is developed first in `sablelinux/development`.
- Once Sable-specific work is validated, its reusable code and a summarized,
  sanitized evidence record are exported here.
- Raw client state, account keys, RPC passwords, downloaded work, slot contents,
  and large build trees never belong in this repository.

See [SYNC_POLICY.md](SYNC_POLICY.md) for the cross-repository workflow.

## Current Kubuntu operating state

- LHC@home is the only attached project.
- The authoritative BOINC data directory is `/var/lib/boinc-client`.
- `boinc-client.service` owns the client process tree.
- `boinc-affinity.service` rotates at most four active BOINC CPUs through
  `0-3`, `4-7`, and `8-11`; logical CPUs `12-13` remain reserved.
- BOINC Manager connects to the service-managed client at
  `127.0.0.1:31416`.

The former root-run client under `/home/pepper` is retired. Do not launch a
second client there.

## Repository layout

```text
config/                  BOINC configuration examples
docs/incidents/          recovery and failure analyses
docs/sablelinux/         SableLinux build/control documentation
docs/testing/            sanitized platform validation
scripts/                 Kubuntu operational and shared scripts
scripts/sablelinux/      SableLinux-specific control scripts
systemd/                 service units and drop-ins
```

## Major documented work

- LHC@home Docker, CVMFS, VirtualBox, ATLAS, CMS, and Theory troubleshooting
- CPU affinity allocation and thermal-load rotation
- BOINC data-directory collision recovery and systemd process ownership
- SableLinux BOINC 8.2.11 source build and manual control layer
- SableLinux Z890 kernel readiness for rootless LHC container work
- Kubuntu kernel 7.0 boot/shutdown regression recovery and stable 6.17 boot pin

The chronological record is in [docs/TIMELINE.md](docs/TIMELINE.md).
