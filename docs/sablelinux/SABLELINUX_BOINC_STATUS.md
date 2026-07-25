# SableLinux BOINC status

## BOINC 8.2.11

SableLinux builds BOINC from pinned upstream commit
`5511380b8980935c25c3ea41df3980445419e59e`. The headless client is installed
under `/opt/boinc/8.2.11`, with `/opt/boinc/current` as the stable path and
`/var/lib/boinc-client` as the state directory.

The corrected client configure profile enables the client and BOINC libraries
while excluding server, Manager, applications, headers, and unit tests. The
important build correction was `--enable-libraries`; package-client/Manager
configure modes were not appropriate for this build.

Exact build details are preserved in `boinc-8.2.11.md`.

## Manual control model

The `boinc-client.service` is deliberately disabled at boot. `boincctl` starts
and stops it on demand, authenticates local RPC as the `boinc` service user,
waits for port 31416 to become ready, and verifies that stop removes both the
process and RPC listener.

The canonical Sable resource policy during initial validation was 50 percent of
14 logical CPUs. The RX 9060 XT was detected through ROCm/OpenCL.

## Validation history

- EliteBook: source client and Manager builds passed; Asteroids ran; MilkyWay
  attachment and scheduling were exercised.
- Z890: BOINC 8.2.11, the manual control layer, RPC readiness, resource policy,
  and RX 9060 XT detection passed.
- Z890 LHC readiness kernel:
  `6.16.1-sable-lhc-test1`, build
  `20260719T211841Z-eb762ba-k6.16.1-sable-lhc-test1`.
  User namespaces, FUSE, and the required kernel primitives passed QEMU and
  physical validation.

## Remaining LHC work

The rootless userspace container stack was not yet installed at the readiness
checkpoint. Remaining work includes subordinate UID/GID allocation for the
`boinc` user, Podman, conmon, an OCI runtime, rootless networking,
fuse-overlayfs, `/run/user/999`, and disposable rootless workload validation.

Detailed work continues in `sablelinux/development`; validated reusable results
are promoted here under the repository sync policy.
