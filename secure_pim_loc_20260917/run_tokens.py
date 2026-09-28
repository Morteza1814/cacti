#!/usr/bin/env python3
"""Run the TT/PT CACTI models and preserve outputs in a fresh directory."""

import argparse
import csv
import hashlib
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def config_value(text, name):
    match = re.search(r"^" + re.escape(name) + r" (\d+)$", text, re.MULTILINE)
    if match is None:
        raise ValueError("Missing numeric setting: " + name)
    return int(match.group(1))


def main():
    model_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cacti", type=Path, default=model_dir.parent / "cacti")
    parser.add_argument("--clock-ns", type=float, default=0.333)
    args = parser.parse_args()
    if not math.isfinite(args.clock_ns) or args.clock_ns <= 0:
        parser.error("--clock-ns must be positive and finite")
    binary = args.cacti.resolve(strict=True)
    tech_dir = (binary.parent / "tech_params").resolve(strict=True)
    run_dir = Path(tempfile.mkdtemp(prefix="secure-pim-token-cacti."))
    (run_dir / "tech_params").symlink_to(tech_dir, target_is_directory=True)
    print("Artifacts: " + str(run_dir), flush=True)

    results = []
    for table, payload_bits in (("tt", 466), ("pt", 146)):
        source = model_dir / (table + ".cfg")
        config = source.read_text()
        data_bytes = config_value(config, "-size (bytes)")
        entry_bytes = config_value(config, "-block size (bytes)")
        if data_bytes % entry_bytes or payload_bits > entry_bytes * 8:
            raise ValueError("Invalid entry sizing: " + str(source))
        entries = data_bytes // entry_bytes
        destination = run_dir / (table + ".cfg")
        shutil.copyfile(source, destination)
        log_path = run_dir / (table + ".log")
        with log_path.open("w") as log:
            result = subprocess.run(
                [str(binary), "-infile", str(destination)], cwd=run_dir,
                stdout=log, stderr=subprocess.STDOUT, timeout=180,
            )
        output = Path(str(destination) + ".out")
        if result.returncode != 0 or not output.is_file():
            raise RuntimeError("CACTI failed or found no model; see " + str(log_path))
        with output.open(newline="") as stream:
            rows = list(csv.DictReader(stream, skipinitialspace=True))
        if len(rows) != 1:
            raise RuntimeError("Expected one CACTI result: " + str(output))
        row = {key.strip(): value.strip() for key, value in rows[0].items()}
        if int(row["Capacity (bytes)"]) != data_bytes:
            raise RuntimeError("CACTI returned an unexpected capacity")
        if int(row["Output width (bits)"]) != entry_bytes * 8:
            raise RuntimeError("CACTI returned an unexpected output width")
        access = float(row["Access time (ns)"])
        cycle = float(row["Random cycle time (ns)"])
        if not all(math.isfinite(value) and value > 0 for value in (access, cycle)):
            raise RuntimeError("CACTI returned invalid timing")
        shutil.copyfile(output, run_dir / f"{table}_{entries}_result.csv")
        results.append({
            "structure": table,
            "entries": entries,
            "tag_bits": 0,
            "payload_bits": payload_bits,
            "padded_data_bytes_per_entry": entry_bytes,
            "data_array_bytes": data_bytes,
            "tag_array_bytes": 0,
            "access_ns": access,
            "access_LOC_cycles": access / args.clock_ns,
            "cycle_ns": cycle,
            "cycle_LOC_cycles": cycle / args.clock_ns,
            "minimum_access_cycles": math.ceil(access / args.clock_ns),
            "minimum_port_interval_cycles": math.ceil(cycle / args.clock_ns),
            "area_mm2": row["Area (mm2)"],
            "search_energy_nJ": "N/A",
            "read_energy_nJ": row["Dynamic read energy (nJ)"],
            "write_energy_nJ": row["Dynamic write energy (nJ)"],
            "leakage_mW": row["Standby leakage per bank(mW)"],
        })
        print(f"{table.upper()}: {entries} entries, access {access:.6f} ns, "
              f"port cycle {cycle:.6f} ns", flush=True)

    summary = run_dir / "token_results.csv"
    with summary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=results[0])
        writer.writeheader()
        writer.writerows(results)
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    (run_dir / "provenance.txt").write_text(
        f"CACTI: {binary}\nSHA256: {digest}\nClock period: {args.clock_ns} ns\n"
    )
    print("Summary: " + str(summary))


if __name__ == "__main__":
    main()
