# Next Steps

The next session begins with research and planning, not installation.

1. Select compatible upstream versions for Podman, conmon, crun, a rootless
   network helper, and fuse-overlayfs.
2. Identify mandatory and optional dependencies.
3. Decide whether netavark, aardvark-dns, and catatonit are required.
4. Record source URLs, release tags, checksums, licenses, and build order.
5. Acquire source archives into the canonical Z890 cache.
6. Build and stage one component at a time.
7. Assign the reviewed BOINC subordinate UID and GID ranges.
8. Create a controlled `/run/user/999` execution environment.
9. Run a disposable rootless Podman smoke test as `boinc`.
10. Validate LHC workload classes individually.
11. Document and commit each successful stage.
12. Export the completed subproject to the separate LHC@home repository only
    after the complete workflow is validated.
