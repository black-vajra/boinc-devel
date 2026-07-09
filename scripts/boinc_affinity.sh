#!/bin/bash

# ─── Configuration ────────────────────────────────────────────────
POLL_INTERVAL=10      # seconds between checks
CPU_THRESHOLD=20.0    # minimum %CPU to be considered a compute worker
MIN_CORES=2           # minimum cores to give any single worker
ROTATION_STEP=2       # cores to advance the window each cycle
# ──────────────────────────────────────────────────────────────────

TOTAL_CORES=$(nproc)
declare -A PINNED_PIDS
ROTATION_COUNTER=0

echo "========================================="
echo " BOINC CPU Affinity Manager"
echo " Total cores: $TOTAL_CORES"
echo " CPU threshold: ${CPU_THRESHOLD}%"
echo " Poll interval: ${POLL_INTERVAL}s"
echo " Core allocation: proportional to CPU usage"
echo " Core rotation: every ${POLL_INTERVAL}s, step ${ROTATION_STEP}"
echo " Stop with: Ctrl+C or systemctl stop boinc-affinity.service"
echo "========================================="
echo ""

get_client_pid() {
    for pid in $(pgrep -x "boinc" 2>/dev/null); do
        if pgrep -P "$pid" > /dev/null 2>&1; then
            echo "$pid"
            return
        fi
    done

    pgrep -x "boinc" 2>/dev/null | head -1
}

get_descendants() {
    local parent=$1
    local children

    children=$(pgrep -P "$parent" 2>/dev/null)

    for child in $children; do
        echo "$child"
        get_descendants "$child"
    done
}

get_lhc_extra_pids() {
    # ATLAS native workers and LHC/CMS VirtualBox workers that may not always
    # appear cleanly under the BOINC process tree.
    pgrep -f "runargs|EVNTtoHITS|AtlasG4|Sim_tf|Gen_tf|python.*atlas|python.*cern|VBoxHeadless.*boinc_|vboxwrapper|wrapper_.*x86_64-pc-linux-gnu" 2>/dev/null
}

get_binary_name() {
    local pid=$1
    local exe

    exe=$(readlink -f "/proc/$pid/exe" 2>/dev/null)

    if [ -n "$exe" ]; then
        basename "$exe"
    else
        ps -p "$pid" -o comm= 2>/dev/null
    fi
}

get_compute_workers() {
    local all_pids=("$@")

    for pid in "${all_pids[@]}"; do
        local cpu

        [ -z "$pid" ] && continue
        [ ! -d "/proc/$pid" ] && continue

        cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ')
        [ -z "$cpu" ] && continue

        if echo "$cpu $CPU_THRESHOLD" | awk '{exit !($1 > $2)}'; then
            echo "$pid"
        fi
    done
}

make_core_list() {
    local start=$1
    local count=$2
    local total=$3
    local -a cores=()

    # If this worker gets all cores, use compact full-range syntax.
    if [ "$count" -ge "$total" ]; then
        echo "0-$((total - 1))"
        return
    fi

    for ((j = 0; j < count; j++)); do
        cores+=( $(( (start + j) % total )) )
    done

    local IFS=,
    echo "${cores[*]}"
}

assign_cores() {
    local workers=("$@")
    local count=${#workers[@]}

    if [ "$count" -eq 0 ]; then
        echo "  $(date +%H:%M:%S) | No active compute workers found above ${CPU_THRESHOLD}% CPU - waiting..."
        return
    fi

    local -a cpu_vals
    local total_cpu=0

    for pid in "${workers[@]}"; do
        local cpu

        cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ')
        cpu=${cpu:-1}

        cpu_vals+=("$cpu")
        total_cpu=$(echo "$total_cpu + $cpu" | bc)
    done

    # Avoid divide-by-zero if ps briefly reports nonsense.
    if echo "$total_cpu" | awk '{exit !($1 <= 0)}'; then
        total_cpu=1
    fi

    local core_cursor=$(( ROTATION_COUNTER % TOTAL_CORES ))

    echo "  $(date +%H:%M:%S) | Allocating $TOTAL_CORES cores proportionally across $count worker(s) (total CPU: ${total_cpu}%, rotation offset: ${core_cursor}):"

    for i in "${!workers[@]}"; do
        local pid=${workers[$i]}
        local cpu=${cpu_vals[$i]}
        local name
        local allocated
        local cpuset

        [ ! -d "/proc/$pid" ] && continue

        name=$(get_binary_name "$pid")

        allocated=$(echo "$cpu $total_cpu $TOTAL_CORES $MIN_CORES" | awk '{
            prop = int(($1 / $2) * $3)
            if (prop < $4) prop = $4
            if (prop > $3) prop = $3
            print prop
        }')

        cpuset=$(make_core_list "$core_cursor" "$allocated" "$TOTAL_CORES")

        echo "  $(date +%H:%M:%S) | '$name' (PID $pid, ${cpu}% CPU) → cores $cpuset ($allocated cores)"

        taskset -cp "$cpuset" "$pid" > /dev/null 2>&1
        renice -n 19 -p "$pid" > /dev/null 2>&1

        PINNED_PIDS[$pid]="$cpuset"
        core_cursor=$(( (core_cursor + allocated) % TOTAL_CORES ))
    done

    echo ""
}

# ─── Main Loop ────────────────────────────────────────────────────
while true; do

    CLIENT_PID=$(get_client_pid)

    if [ -z "$CLIENT_PID" ]; then
        echo "$(date +%H:%M:%S) | boinc process not found - waiting..."
        sleep "$POLL_INTERVAL"
        continue
    fi

    mapfile -t ALL_DESCENDANTS < <(
        {
            get_descendants "$CLIENT_PID"
            get_lhc_extra_pids
        } | sort -u
    )

    mapfile -t COMPUTE_WORKERS < <(
        get_compute_workers "${ALL_DESCENDANTS[@]}"
    )

    CHANGED=false

    for pid in "${COMPUTE_WORKERS[@]}"; do
        if [ -z "${PINNED_PIDS[$pid]+x}" ]; then
            CHANGED=true
            break
        fi
    done

    for pid in "${!PINNED_PIDS[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            unset "PINNED_PIDS[$pid]"
            CHANGED=true
        else
            local_cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ')

            if [ -z "$local_cpu" ] || ! echo "$local_cpu $CPU_THRESHOLD" | awk '{exit !($1 > $2)}'; then
                unset "PINNED_PIDS[$pid]"
                CHANGED=true
            fi
        fi
    done

    if $CHANGED; then
        echo "$(date +%H:%M:%S) | Change detected — ${#COMPUTE_WORKERS[@]} worker(s) above ${CPU_THRESHOLD}% CPU:"

        for pid in "${COMPUTE_WORKERS[@]}"; do
            name=$(get_binary_name "$pid")
            cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ')
            echo "  → PID $pid : $name (${cpu}% CPU)"
        done

        echo ""

        unset PINNED_PIDS
        declare -A PINNED_PIDS
    fi

    # Always reassign cores every cycle to enforce rotation.
    if [ "${#COMPUTE_WORKERS[@]}" -gt 0 ]; then
        assign_cores "${COMPUTE_WORKERS[@]}"
    fi

    ROTATION_COUNTER=$(( ROTATION_COUNTER + ROTATION_STEP ))

    sleep "$POLL_INTERVAL"

done
