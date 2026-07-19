#!/bin/bash

# ─── Configuration ────────────────────────────────────────────────
POLL_INTERVAL=10      # seconds between checks
CPU_THRESHOLD=20.0    # minimum %CPU to be considered a compute worker
MIN_CORES=2           # preferred minimum; reduced fairly if the pool cannot satisfy it
ROTATION_STEP=2       # cores to advance the window each cycle
MAX_MANAGED_CORES=11     # logical CPU cores BOINC workers may use; remaining cores stay free
# ──────────────────────────────────────────────────────────────────

SYSTEM_CORES=$(nproc)

if [ "$MAX_MANAGED_CORES" -gt 0 ] && [ "$MAX_MANAGED_CORES" -lt "$SYSTEM_CORES" ]; then
    TOTAL_CORES="$MAX_MANAGED_CORES"
else
    TOTAL_CORES="$SYSTEM_CORES"
fi
declare -A PINNED_PIDS
ROTATION_COUNTER=0

echo "========================================="
echo " BOINC CPU Affinity Manager"
echo " System cores: $SYSTEM_CORES"
echo " Managed BOINC cores: $TOTAL_CORES"
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

calculate_core_counts() {
    local total=$1
    local preferred_min=$2
    local tie_start=$3
    shift 3

    # Return one allocation count per CPU value. When the preferred minimum
    # cannot fit, lower it just enough to keep every worker inside the pool.
    # Remaining cores use weighted highest averages. The rotating tie start
    # prevents equal-load workers from always losing the extra core.
    printf '%s\n' "$@" | awk \
        -v total="$total" \
        -v preferred_min="$preferred_min" \
        -v tie_start="$tie_start" '
        NF {
            cpu[n] = $1 + 0
            if (cpu[n] <= 0) cpu[n] = 1
            n++
        }
        END {
            if (n == 0) exit

            effective_min = preferred_min
            if ((n * effective_min) > total) {
                effective_min = int(total / n)
            }
            if (effective_min < 1) effective_min = 1

            # More workers than cores cannot be placed uniquely. Give each
            # worker one controlled core; assign_cores() warns before applying
            # those necessarily shared placements.
            if (n > total) {
                for (i = 0; i < n; i++) print 1
                exit
            }

            remaining = total - (n * effective_min)
            for (i = 0; i < n; i++) {
                allocation[i] = effective_min
                extras[i] = 0
            }

            tie_start %= n
            while (remaining > 0) {
                best = -1
                best_score = -1

                for (j = 0; j < n; j++) {
                    i = (tie_start + j) % n
                    score = cpu[i] / (extras[i] + 1)
                    if (score > best_score) {
                        best = i
                        best_score = score
                    }
                }

                allocation[best]++
                extras[best]++
                remaining--
            }

            for (i = 0; i < n; i++) print allocation[i]
        }'
}

assign_cores() {
    local workers=("$@")
    local count=${#workers[@]}

    if [ "$count" -eq 0 ]; then
        echo "  $(date +%H:%M:%S) | No active compute workers found above ${CPU_THRESHOLD}% CPU - waiting..."
        return
    fi

    local -a cpu_vals
    local -a allocations
    local total_cpu=0
    local allocated

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

    mapfile -t allocations < <(
        calculate_core_counts \
            "$TOTAL_CORES" \
            "$MIN_CORES" \
            "$(( ROTATION_COUNTER % count ))" \
            "${cpu_vals[@]}"
    )

    if [ "${#allocations[@]}" -ne "$count" ]; then
        echo "  $(date +%H:%M:%S) | FAIL: allocation planner returned ${#allocations[@]} count(s) for $count worker(s); skipping this cycle"
        return 1
    fi

    local effective_min=$MIN_CORES
    local allocation_mode="without overlap"

    if [ $(( count * MIN_CORES )) -gt "$TOTAL_CORES" ]; then
        effective_min=$(( TOTAL_CORES / count ))
        [ "$effective_min" -lt 1 ] && effective_min=1

        echo "  $(date +%H:%M:%S) | WARN: preferred minimum ${MIN_CORES} cannot fit $count workers in $TOTAL_CORES cores; using effective minimum $effective_min"
    fi

    if [ "$count" -gt "$TOTAL_CORES" ]; then
        allocation_mode="with controlled one-core sharing"
        echo "  $(date +%H:%M:%S) | WARN: $count workers exceed the $TOTAL_CORES-core pool; one-core sharing is unavoidable"
    else
        local allocation_total=0

        for allocated in "${allocations[@]}"; do
            allocation_total=$(( allocation_total + allocated ))
        done

        if [ "$allocation_total" -ne "$TOTAL_CORES" ]; then
            echo "  $(date +%H:%M:%S) | FAIL: planned allocation totals $allocation_total instead of $TOTAL_CORES; skipping this cycle"
            return 1
        fi
    fi

    echo "  $(date +%H:%M:%S) | Allocating $TOTAL_CORES cores $allocation_mode across $count worker(s) (total CPU: ${total_cpu}%, rotation offset: ${core_cursor}):"

    for i in "${!workers[@]}"; do
        local pid=${workers[$i]}
        local cpu=${cpu_vals[$i]}
        local name
        local cpuset

        [ ! -d "/proc/$pid" ] && continue

        name=$(get_binary_name "$pid")

        allocated=${allocations[$i]}

        cpuset=$(make_core_list "$core_cursor" "$allocated" "$TOTAL_CORES")

        echo "  $(date +%H:%M:%S) | '$name' (PID $pid, ${cpu}% CPU) → cores $cpuset ($allocated cores)"

        taskset -acp "$cpuset" "$pid" > /dev/null 2>&1
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
