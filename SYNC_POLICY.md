# Cross-repository synchronization policy

## Repositories

- `black-vajra/boinc-devel`, branch `main`: reusable BOINC material and the
  summarized operational record.
- `black-vajra/sablelinux`, branch `development`: authoritative work-in-progress
  for integrating BOINC into SableLinux.

Each bootable partition keeps a sibling clone at
`/home/pepper/boinc-devel`. Never place a clone inside the `sablelinux` working
tree.

## Promotion workflow

1. Develop and validate SableLinux integration in `sablelinux/development`.
2. Confirm that the SableLinux tree is clean and pushed.
3. Export only BOINC-related tracked material.
4. Scan the export for credentials, RPC secrets, account files, client state,
   downloaded work, slot contents, and oversized evidence.
5. Copy portable scripts exactly; summarize host-specific build and validation
   evidence in `boinc-devel`.
6. Review, commit, and push `boinc-devel/main`.
7. Fast-forward the `boinc-devel` clone on each partition and verify identical
   `HEAD` values.

## Evidence policy

The standalone repository records enough provenance to reproduce decisions:
source commit, version, build flags, relevant paths, service model, test result,
and remaining work. The SableLinux repository retains its detailed integration
evidence. Large raw logs and kernel build artifacts are not duplicated unless
they are essential to a BOINC-specific conclusion.
