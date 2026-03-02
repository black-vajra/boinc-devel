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
echo " Stop with: Ctrl+C (or restart boinc)"
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

get_atlas_pids() {
    pgrep -f "runargs\|EVNTtoHITS\|AtlasG4\|Sim_tf\|Gen_tf\|python.*atlas\|python.*cern" 2>/dev/null
}

get_binary_name() {
    local pid=$1
    basename "$(readlink -f /proc/$pid/exe 2>/dev/null)" 2>/dev/null || \
        ps -p "$pid" -o comm= 2>/dev/null
}

get_compute_workers() {
    local all_pids=("$@")
    for pid in "${all_pids[@]}"; do
        local cpu
        cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ')
        [ -z "$cpu" ] && continue
        if echo "$cpu $CPU_THRESHOLD" | awk '{exit !($1 > $2)}'; then
            echo "$pid"
        fi
    done
}

assign_cores() {
    local workers=("$@")
    local count=${#workers[@]}

    if [ "$count" -eq 0 ]; then
        echo "  $(date +%H:%M:%S) | No active compute workers found (none above ${CPU_THRESHOLD}% CPU) - waiting..."
        return
    fi

    # Collect CPU usage for each worker
    local -a cpu_vals
    local total_cpu=0
    for pid in "${workers[@]}"; do
        local cpu
        cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ')
        cpu=${cpu:-1}
        cpu_vals+=("$cpu")
        total_cpu=$(echo "$total_cpu + $cpu" | bc)
    done

    # Core rotation — shift starting position each cycle
    local core_cursor=$(( ROTATION_COUNTER % TOTAL_CORES ))

    echo "  $(date +%H:%M:%S) | Allocating $TOTAL_CORES cores proportionally across $count worker(s) (total CPU: ${total_cpu}%, rotation offset: ${core_cursor}):"

    for i in "${!workers[@]}"; do
        local pid=${workers[$i]}
        local cpu=${cpu_vals[$i]}
        local name
        name=$(get_binary_name "$pid")

        # Calculate proportional share of cores, minimum MIN_CORES
        local allocated
        allocated=$(echo "$cpu $total_cpu $TOTAL_CORES $MIN_CORES" | awk '{
            prop = int(($1 / $2) * $3)
            if (prop < $4) prop = $4
            print prop
        }')

        local start=$core_cursor
        local end=$(( core_cursor + allocated - 1 ))

        # Wrap around if we exceed total cores
        if [ "$end" -ge "$TOTAL_CORES" ]; then
            end=$(( TOTAL_CORES - 1 ))
        fi

        # Last worker gets all remaining cores in the window
        if [ "$i" -eq $(( count - 1 )) ]; then
            end=$(( TOTAL_CORES - 1 ))
            # If we've wrapped, give from start to end of available range
            if [ "$start" -ge "$TOTAL_CORES" ]; then
                start=0
                end=$(( allocated - 1 ))
            fi
        fi

        echo "  $(date +%H:%M:%S) | '$name' (PID $pid, ${cpu}% CPU) → cores $start-$end ($allocated cores)"
        taskset -cp "$start-$end" "$pid" > /dev/null 2>&1
        # Also renice to ensure ATLAS/heavy workers stay low priority
        renice -n 19 -p "$pid" > /dev/null 2>&1

        PINNED_PIDS[$pid]="$start-$end"
        core_cursor=$(( end + 1 ))

        # If we've run out of cores, wrap remaining workers to full range
        if [ "$core_cursor" -ge "$TOTAL_CORES" ]; then
            core_cursor=0
        fi
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

    mapfile -t ALL_DESCENDANTS < <({ get_descendants "$CLIENT_PID"; get_atlas_pids; } | sort -u)
    mapfile -t COMPUTE_WORKERS < <(get_compute_workers "${ALL_DESCENDANTS[@]}")

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

    # Always reassign cores every cycle to enforce rotation
    if [ "${#COMPUTE_WORKERS[@]}" -gt 0 ]; then
        assign_cores "${COMPUTE_WORKERS[@]}"
    fi

    # Advance rotation counter
    ROTATION_COUNTER=$(( ROTATION_COUNTER + ROTATION_STEP ))

    sleep "$POLL_INTERVAL"

done
