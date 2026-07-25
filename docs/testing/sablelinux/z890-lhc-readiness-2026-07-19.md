# Z890 LHC Kernel and Rootless-Container Readiness

## Authority

This record was generated on the canonical SableLinux Z890 build and release
host.

Build ID: `20260719T211841Z-eb762ba-k6.16.1-sable-lhc-test1`

Source repository commit: `eb762ba46c313f8dfdb0ff6de7ab84b39bc27178`

Validated kernel: `6.16.1-sable-lhc-test1`

## Completed kernel engineering

The kernel was rebuilt from clean Linux 6.16.1 sources with:

- `CONFIG_USER_NS=y`
- `CONFIG_FUSE_FS=m`
- `CONFIG_IKCONFIG=y`
- `CONFIG_IKCONFIG_PROC=y`
- local version `-sable-lhc-test1`

The candidate completed clean compilation, staged-module validation,
installed-root initramfs generation, direct QEMU/KVM Tier 1 testing, parallel
installation, dedicated non-default GRUB configuration, and physical runtime
validation on the canonical Z890 host.

Physical validation confirmed unprivileged user namespaces, FUSE,
`/dev/fuse`, storage, KVM, DRM, AMD KFD, audio, networking, systemd,
artifact integrity, and compatibility-kernel rollback protection.

The physical validator recorded zero failed checks.

## Validator corrections

Two validator defects were identified without invalidating the runtime result:

1. The runtime report hashed itself while `tee` was still appending output,
   making the printed value an intermediate hash.
2. BusyBox `ip` does not support `ip -brief link`. Network state was
   revalidated through sysfs, `ip addr show`, and `ip route`.

## Rootless Podman readiness

The kernel and host facilities required for rootless containers work:

- unprivileged user namespaces;
- unified cgroup v2;
- FUSE and `/dev/fuse`;
- writable BOINC home;
- setuid `newuidmap` and `newgidmap`.

Seven required userspace or configuration categories remain:

1. BOINC subordinate UID range.
2. BOINC subordinate GID range.
3. Podman.
4. conmon.
5. An OCI runtime such as crun or runc.
6. A rootless network helper such as pasta or slirp4netns.
7. fuse-overlayfs.

The advisory collision-free subordinate range is:

- `/etc/subuid`: `boinc:131072:65536`
- `/etc/subgid`: `boinc:131072:65536`

No subordinate-ID files were modified.

## Local-source discovery

No usable Podman-stack source archives were found in the canonical source or
download caches. The reported filename matches were false positives involving
unrelated names such as `passthrough`, `truncate`, and `runcmd`.

## Current boundary

The kernel phase is complete. The container phase has not begun.

No subordinate-ID assignments, container packages, runtime directories,
storage state, network configuration, or BOINC service changes were made.

## Repository export policy

This work remains authoritative in the SableLinux repository during
development.

The completed BOINC/LHC subproject will also be exported to the separate
LHC@home GitHub repository, but only after Podman and LHC workload validation
are finished. Interim state must not be published there as a completed
subproject.
