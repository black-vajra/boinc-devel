#!/bin/bash
# A short systemd timer action, with no resident watcher process.
set -eu

if ! systemctl is-active --quiet boinc-client.service; then
    systemctl stop boinc-affinity.service
    exit 0
fi

if python3 /usr/local/libexec/boinc/lhc_affinity.py check; then
    systemctl start boinc-affinity.service
else
    status=$?
    systemctl stop boinc-affinity.service
    [ "$status" -eq 1 ] && exit 0
    exit "$status"
fi
