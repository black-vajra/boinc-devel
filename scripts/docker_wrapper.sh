#!/bin/bash
# Wrapper: injects --privileged --user 122:127 into docker run/create
# Workaround for docker-ce 29.x + BOINC 8.2.8 LHC@home tmpfs incompatibility
# Real binary: /usr/bin/docker.real (managed by dpkg-divert)
# Deployment: dpkg-divert --add --no-rename --divert /usr/bin/docker.real /usr/bin/docker
# Removal: dpkg-divert --remove --no-rename /usr/bin/docker
# See: docs/LHC_DOCKER_COMPATIBILITY.md

REAL_DOCKER=/usr/bin/docker.real

if [[ "$1" == "run" || "$1" == "create" ]]; then
    exec "$REAL_DOCKER" "$1" --privileged --user 122:127 "${@:2}"
fi

exec "$REAL_DOCKER" "$@"
