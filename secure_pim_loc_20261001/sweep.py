#!/usr/bin/env python3
"""Sweep LOC table sizes using full-width identifiers; retain raw CACTI output."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile


MODELS = Path(__file__).resolve().parent
SIZES = {
    "cc": [64, 128, 256, 512, 1024],
    "oc": [32, 64, 128, 256, 512, 1024],
    "rt": [32, 64, 128, 256, 512, 1024],
    "tt": [2**power for power in range(5, 17)],
    "pt": [2**power for power in range(5, 17)],
}


def numeric_setting(config, key):
    match = re.search("^" + re.escape(key) + r" (\d+)$", config, re.MULTILINE)
    if match is None:
        raise ValueError("Missing CACTI setting: " + key)
    return int(match[1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cacti", type=Path, required=True)
    parser.add_argument("--clock-ns", type=float, default=0.333)
    parser.add_argument("--tables", nargs="+", choices=SIZES, default=list(SIZES))
    parser.add_argument("--entries", nargs="+", type=int,
                        help="Override the default power-of-two sweep")
    parser.add_argument("--outdir", type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.clock_ns) or args.clock_ns <= 0:
        parser.error("--clock-ns must be positive and finite")
    if args.entries is not None and any(n <= 0 for n in args.entries):
        parser.error("--entries must be positive")
    binary = args.cacti.resolve(strict=True)
    tech = (binary.parent / "tech_params").resolve(strict=True)
    if args.outdir:
        out = args.outdir.resolve()
        out.mkdir(parents=True, exist_ok=False)
    else:
        out = Path(tempfile.mkdtemp(prefix="loc-table-cacti-"))
    (out / "tech_params").symlink_to(tech, target_is_directory=True)
    provenance = {
        "cacti": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "clock_ns": args.clock_ns, "config_sha256": {},
    }
    print("CACTI artifacts: " + str(out), flush=True)
    with (out / "results.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["table", "entries", "entry_bytes", "tag_bits", "access_ns",
                         "cycle_ns", "access_fits", "cycle_fits", "area_mm2", "status"])
        for table in args.tables:
            config = (MODELS / (table + ".cfg")).read_text()
            provenance["config_sha256"][table] = hashlib.sha256(config.encode()).hexdigest()
            width = numeric_setting(config, "-block size (bytes)")
            tag = 0 if table in ("tt", "pt") else numeric_setting(config, "-tag size (b)")
            for entries in args.entries or SIZES[table]:
                # This CACTI requires at least 64 data bytes per bank.
                if entries * width < 64:
                    continue
                cfg = out / f"{table}-{entries}.cfg"
                cfg.write_text(re.sub(r"^-size \(bytes\) .*$",
                                      "-size (bytes) " + str(entries * width),
                                      config, flags=re.MULTILINE))
                log_path = cfg.with_suffix(".log")
                with log_path.open("w") as log:
                    result = subprocess.run([str(binary), "-infile", str(cfg)], cwd=out,
                                            stdout=log, stderr=subprocess.STDOUT, timeout=180)
                raw = Path(str(cfg) + ".out")
                if not raw.is_file():
                    log = log_path.read_text()
                    if not any(message in log for message in (
                            "ERROR: no cache organizations met optimization criteria",
                            "ERROR: no valid data array organizations found")):
                        raise RuntimeError("CACTI failed; see " + str(log_path))
                    row = [table, entries, width, tag, "", "", "", "", "", "no_model"]
                else:
                    if result.returncode:
                        raise RuntimeError("CACTI failed; see " + str(log_path))
                    with raw.open() as source:
                        rows = list(csv.DictReader(source, skipinitialspace=True))
                    if len(rows) != 1:
                        raise RuntimeError("Expected one CACTI result: " + str(raw))
                    values = {key.strip(): value.strip() for key, value in rows[0].items()}
                    if (int(values["Capacity (bytes)"]) != entries * width or
                            int(values["Output width (bits)"]) != width * 8):
                        raise RuntimeError("CACTI returned unexpected dimensions: " + str(raw))
                    access = float(values["Access time (ns)"])
                    cycle = float(values["Random cycle time (ns)"])
                    if not all(math.isfinite(value) and value > 0 for value in (access, cycle)):
                        raise RuntimeError("CACTI returned invalid timing: " + str(raw))
                    row = [table, entries, width, tag, access, cycle,
                           access <= args.clock_ns, cycle <= args.clock_ns,
                           values["Area (mm2)"], "ok"]
                writer.writerow(row)
                stream.flush()
                print(",".join(map(str, row)), flush=True)
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


if __name__ == "__main__":
    main()
