# Kubuntu kernel boot and shutdown recovery — 2026-07-25

## Incident

On the Z890 workstation, kernel `7.0.0-28-generic` accepted the LUKS password
and then remained at the Kubuntu splash for more than ten minutes. A cold boot
was required. Earlier multi-day sessions had also failed to complete shutdown.

## Evidence and assessment

The failed 7.0 boot contained an AMDGPU NULL-pointer/page-fault path with module
loader contention. Shutdown evidence reached `poweroff.target` but repeatedly
reported:

```text
amdgpu REG_WAIT timeout ... optc401_disable_crtc
```

The strongest working diagnosis is a kernel-7.0 AMDGPU/ACPI display teardown
regression, rather than LUKS failure, filesystem exhaustion, or a missing
initramfs. The encrypted root unlocked successfully, filesystems had ample
space and inodes, and kernel `6.17.0-40-generic` booted without the comparable
oops/lockup.

## Recovery

GRUB was configured to select the 6.17 advanced entry by stable menu IDs:

```text
gnulinux-advanced-affff63a-c833-4b7c-abf2-3363dbbbb794>gnulinux-6.17.0-40-generic-advanced-affff63a-c833-4b7c-abf2-3363dbbbb794
```

The menu remains visible for five seconds. The exact 6.17 image, modules, and
extra-modules packages were marked manually installed.

Marking packages manual protects this known-good kernel from `autoremove`; it
does not prevent APT from installing a newer kernel. GRUB remains pinned to
6.17 until a later kernel is explicitly tested.
