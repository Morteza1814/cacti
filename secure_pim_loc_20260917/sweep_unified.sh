#!/usr/bin/env bash
# Sweep power-of-two capacities; retain all raw output outside the repository.
set -euo pipefail
model_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cacti_bin=$(realpath -- "${1:-$model_dir/../cacti}")
run_dir=$(mktemp -d /tmp/secure-pim-cacti-sweep.XXXXXX)
ln -s "$(dirname -- "$cacti_bin")/tech_params" "$run_dir/tech_params"
cd "$run_dir"
printf 'cache,entries,data_bytes,access_ns,cycle_ns,access_cycles,meets_access_target\n' | tee results.csv
for cache in ur; do
    block=$(awk '/^-block size / {print $4}' "$model_dir/$cache.cfg")
    for entries in 8 16 32 64 128 256 512 1024 2048 4096 8192; do
        # CACTI requires at least 64 bytes of data per bank.
        if (( entries * block < 64 )); then continue; fi
        cfg="$run_dir/$cache-$entries.cfg"
        sed "s/^-size (bytes) .*/-size (bytes) $((entries * block))/" \
            "$model_dir/$cache.cfg" > "$cfg"
        result=0
        "$cacti_bin" -infile "$cfg" > "$cfg.log" 2>&1 || result=$?
        if ! test -s "$cfg.out"; then
            if grep -Eq 'ERROR: no (cache organizations met optimization criteria|valid data array organizations found)' "$cfg.log"; then
                printf '%s,%d,%d,,,,no_model\n' "$cache" "$entries" "$((entries * block))" | tee -a results.csv
                continue
            fi
            echo "No CACTI result: $cfg.log" >&2
            exit 1
        fi
        if (( result != 0 )); then
            echo "CACTI failed with status $result: $cfg.log" >&2
            exit "$result"
        fi
        awk -F, -v cache="$cache" -v entries="$entries" -v bytes="$((entries * block))" '
            NR == 1 {
                for (i=1; i<=NF; i++) {
                    if ($i ~ /Access time/) access=i;
                    if ($i ~ /Random cycle time/) cycle=i;
                }
                if (!access || !cycle) exit 1;
                next;
            }
            NR == 2 {
                printf "%s,%d,%d,%.6f,%.6f,%.9f,%s\n", cache, entries, bytes,
                    $access, $cycle, $access / 0.333,
                    ($access <= 0.333 ? "yes" : "no");
            }
        ' "$cfg.out" | tee -a results.csv
    done
done
printf 'Raw configs/logs and results: %s\n' "$run_dir" >&2
