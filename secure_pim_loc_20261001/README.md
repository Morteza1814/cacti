# LOC table sizing, 2026-10-01

These models preserve the implementation's **32-bit TEE/process tokens and
64-bit object/request IDs**. Earlier estimates in `~/GIT/cacti/secure_pim_loc_20260917`
used 16-bit identifiers; those results cannot justify the same capacities with
the current wider keys. The request table is abbreviated **RT**.

## Packed hardware entries

These are hardware encodings, excluding C++ pointers/container overhead. CC/OC/RT
use fully associative CAM+SRAM, one search port and one RW port. TT/PT use indexed
SRAM with one shared RW port. All models use a full padded entry output.

| Table | Tag bits | Data fields, in bits | Padded bytes/entry |
| --- | ---: | --- | ---: |
| CC | 128 | permissions6 + backingPresent1 | 1 |
| OC | 64 | owner64 + physicalBase64 + logicalSize64 + physicalSize64 + inFlight64 + state1 + dirty1 + backingPresent1 | 64 |
| RT | 64 | completion64 + status64 + owner64 + state2 + objectIds[3]×64 + opcode8 + length64 + deviceBases[3]×64 | 128 |
| TT | 0 | teeId64 + teeToken32 + channelKey256 + txSequence64 + rxSequence64 + state2 | 64 |
| PT | 0 | teeId64 + processId64 + processToken32 + state2 | 32 |

CC's key is `{TEE32, process32, objectId64}`. The six defined permissions fit
alongside backing presence in one byte; unused permission bits have no modeled
function. OC and RT use objectId64 and requestId64 respectively. Reserved ID zero
marks empty slots; this requires zero lookup rejection and publishing a nonzero
key only after its payload is ready. TT/PT use their state field for occupancy.
OC retains the full software counter width; narrowing inFlight to the request
capacity bound would still require the same padded 64-byte entry.

TT/PT retain the previous design's storage allowances for instance identity,
channel keys and counters. The simulator does **not** implement authenticated
provisioning/channel cryptography. These estimates assume a trusted slot index
is available: identity-to-slot mapping, comparison and allocation are external.
They estimate the proposed storage, not the full token-management path.

## Results and candidate configurations

The runners configure nominal 3 GHz, recorded by gem5 as **333 ps per cycle**.
All values below are ns. Access time is read/search-to-result latency; port
cycle time is the minimum spacing of successive accesses on the same port.

| Table | Previous entries | Candidate entries | Access ns | Read cycles, rounded up | Port cycle ns | Minimum port interval, cycles |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CC | 64 | 64 | 0.323296 | 1 | 0.294174 | 1 |
| OC | 64 | 64 | 0.303868 | 1 | 0.519014 | 2 |
| RT | 64 | 64 | 0.496566 | 2 | 1.270890 | 4 |
| TT | 32 | 512 | 0.218655 | 1 | 0.223493 | 1 |
| PT | 256 | 1024 | 0.219072 | 1 | 0.223493 | 1 |

`sweep_results.csv` records every tested size, including failures to find an
organization. The selected raw outputs are also included. Under these fixed
settings:

- CC at 128 entries already needs 0.349316 ns; 256 needs 0.398839 ns.
- OC at 128 returns no valid organization, which is not a proof that every
  hardware implementation fails. At 256, access is 0.401647 ns. There is no
  evidence here supporting a larger tested one-cycle OC.
- RT already exceeds one cycle at 64. Keeping this encoding would require a
  two-cycle read, plus the separate owner/state check. It does not meet the
  one-cycle target. Compact CAM and indexed-SRAM alternatives were evaluated
  separately in [the RT entry-sizing study](rt_entry_sizing/README.md); no RT
  redesign is implemented by these CACTI files.
- TT at 1024 and PT at 2048 fit a one-cycle read (0.292127 / 0.292572 ns), but
  their port cycle is 0.438380 ns. TT512/PT1024 are the largest tested powers of
  two meeting **both** targets, consistent with the current TT/PT port model.

These are CACTI array estimates, not physical timing closure; for example CC64
has only 9.704 ps of access margin. They exclude replacement/free-slot selection,
allocator metadata, full-table scheduling scans and external controller wiring.
The timing model charges validation separately. **Writes remain an explicit
one-cycle assumption**, because this output does not provide separately
calibrated write latency. CC/OC/RT port contention remains unmodeled; OC's
two-cycle and RT's four-cycle issue intervals must not be reported as implemented
throughput. TT/PT do serialize accesses on their respective shared ports.
Backing CT/OT are software maps with separate provisional memory costs; these
on-chip estimates do not size them or make their accesses one cycle.

## Reproduction and tuning

All configurations retain the earlier study's 22-nm HP cells/periphery, 360 K,
one bank, UCA, Global_30 signaling, conservative semi-global wiring, no ECC or
power gating, and minimum-access-delay optimization with a 20% deviation filter.
CC/OC/RT use fast access; TT/PT use normal scratch-RAM access. The inherited DDR
IO/MemCAD settings do not determine the SRAM timing.

From the CACTI repository:

```sh
python3 secure_pim_loc_20261001/sweep.py \
  --cacti ./cacti
```

The runner writes configs, logs, raw outputs, a CSV and binary/config hashes to
a fresh temporary directory. It leaves the external CACTI checkout unchanged.
Use `--tables tt pt --entries 512 1024 2048` for a smaller sweep, or
`--clock-ns` for another clock period. `no_model` is a rejected organization,
not a measured access time. The recorded binary SHA256 is
`85b98f8f25e6772ae6b5288f881f41b3b1525a1b0b915f15d7243ff8a1d41db7`.

These files do not change gem5 capacities, cycle budgets or table organization.
Capacity and latency are independent modeling choices: changing a capacity does
**not** rerun CACTI or automatically adjust latency. Recheck the entry widths,
clock and port assumptions before applying any candidate to the simulator.

## Earlier capability-cache experiments

The repository-root `cc_l1.cfg`, `cc_l2.cfg`, and `cc_monolithic.cfg` retain
earlier cache experiments. Their `.cfg.out` files contain accumulated capacity
sweeps; each output row states its own capacity and need not match the current
configuration file. Those layouts differ from the full-width LOC table models
in this directory and should not be used to infer the current table limits.
