#!/bin/bash
# LHC-only affinity. The watcher starts this only for an executing LHC task.
set -eu

POLL_INTERVAL=10
ROTATION_STEP=4
MAX_MANAGED_CORES=4
ROTATION_POOL_CORES=14

HELPER=/usr/local/libexec/boinc/lhc_affinity.py

# Also guard manual starts and old BOINC startup scripts.
if python3 "$HELPER" check; then
    exec python3 "$HELPER" manage \
        --interval "$POLL_INTERVAL" \
        --step "$ROTATION_STEP" \
        --cores "$MAX_MANAGED_CORES" \
        --pool "$ROTATION_POOL_CORES"
else
    status=$?
    [ "$status" -eq 1 ] && exit 0
    exit "$status"
fi
