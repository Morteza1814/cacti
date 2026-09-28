# TEE and process token tables (TT/PT)

These are standalone CACTI sizing proposals for the trusted token registries.
TT has 32 entries; PT has 256 entries total across all TEEs. These are initial
capacity choices, not a claim of optimal sizing. Count every live registration,
including suspended processes and entries awaiting teardown. Neither table has
a backing store. This addition does not implement TT/PT or change gem5 timing.

## Packed entries

Field widths are bits. The 16-bit tokens match this directory's existing
TEE16/process16 CC, OC and UR sizing proposal. The gem5 prototype instead packs
two 32-bit tokens into a 64-bit identity; these configs do not truncate them.

| TT field | Bits | Meaning |
|---|---:|---|
| teeId | 64 | Trusted TEE-instance identity, checked after indexed access |
| teeToken | 16 | TEE identity used by the capability lookup |
| channelKey | 256 | Symmetric key for the authenticated TEE-PDP control channel |
| txSequence | 64 | Outgoing channel sequence/nonce counter |
| rxSequence | 64 | Last accepted incoming sequence for an ordered channel |
| state | 2 | Free / Active / Revoking; fourth encoding reserved and rejected |
| **Total** | **466** | 59 bytes rounded to a **64-byte CACTI line** |

| PT field | Bits | Meaning |
|---|---:|---|
| teeId | 64 | Parent TEE-instance identity; parent must have an active TT entry |
| processId | 64 | Trusted process-instance identity within that TEE |
| processToken | 16 | Process identity used with the TEE token by capability lookup |
| state | 2 | Free / Active / Revoking; fourth encoding reserved and rejected |
| **Total** | **146** | 19 bytes rounded to a **32-byte CACTI line** |

TEE/process instance identities distinguish lifetimes, rather than using a
recycled OS PID as the identity. The TT channel key and replay counters are
included inline, so their storage is not hidden in an unmodeled key table.
The two counters assume an ordered channel with a single receiver sequence;
out-of-order replay windows, extra directional keys and protocol-specific state
would require a revised encoding. Cryptographic engines and authenticated
enrollment are not modeled by these SRAM arrays.

Free state marks an unused slot; there is no additional valid bit. A free slot
index may be reused, but tokens must not wrap or be reused while an old
capability, saved token register or request could still reference them. For the
16-bit-token sizing proposal, fail closed before token exhaustion. Generation
bits, if adopted, must be carried and checked throughout the identity path;
adding a generation only to TT/PT would be insufficient.

## Access and lifecycle assumptions

Both tables use indexed SRAM: one shared read/write port, one bank, no search
port, no stored CAM tag, full-entry output. The trusted PDP/context-switch path
supplies a slot index, then validates the stored identity and state. The slot
indices need 5 bits (TT) and 8 bits (PT); they are addresses, not extra row tags.
The logical lookup keys are teeId for TT and (teeId, processId) for PT, stored
inside the rows. Locating a slot from arbitrary identities requires a separate
trusted handle mapping or a scan; the reported access time covers only one
indexed array access, not that operation or the identity comparison.

Use these tables at enrollment, trusted context switches and teardown. Normal
PIM authorization uses the loaded tokens and CC/CT, so it does not inherently
need an extra TT/PT access per operand. Reads and writes share a port and must
be serialized. There is no cache replacement or LRU eviction of live entries.
On capacity exhaustion, reject/retry registration. Apply per-TEE process quotas
in the admission logic when isolation against registration exhaustion matters.

Revoking entries block new use. Before reclaiming a slot, invalidate dependent
capabilities and saved register contexts, drain/cancel outstanding requests,
and erase secret state. Parent TT teardown includes its PT entries. Enrollment,
index validation, state transitions, allocation, quotas, synchronization and
zeroization control are implementation requirements, not functionality provided
or proven by CACTI. The current SE-mode gem5 token-loading m5op is only a stand-in
for privileged context management.

## Results

Settings match the existing package: 22-nm HP cells/periphery, 360 K, UCA,
conservative semi-global wiring, Global_30 signaling, no ECC or power gating.
Unlike CC/OC/UR CAM+SRAM models, these use normal scratch-RAM access, associativity
1, one RW port and zero search ports. The inherited `-tag size "default"` is
ignored for scratch RAM; CACTI may print a default width without allocating a
tag array. DDR IO/MemCAD output is unrelated to these on-chip array estimates.

| Table | Entries | Bytes/entry | Data bytes | Access ns | Port cycle ns | Area mm2 |
|---|---:|---:|---:|---:|---:|---:|
| TT | 32 | 64 | 2048 | 0.102940 | 0.138149 | 0.00802175 |
| PT | 256 | 32 | 8192 | 0.128271 | 0.155009 | 0.00910497 |

Combined data storage is 10 KiB. At the existing 0.333-ns LOC period, both
access and same-port cycle estimates fit one cycle. These are CACTI estimates,
not timing closure or measurements of complete context-switch/authentication
latency. No separate write latency is inferred from the reported access time.

`token_results.csv` records sizing, timing, area, read/write energy and leakage.
`tt_32_result.csv` and `pt_256_result.csv` preserve the raw selected results.
The CACTI binary SHA256 is
`85b98f8f25e6772ae6b5288f881f41b3b1525a1b0b915f15d7243ff8a1d41db7`.

## Reproduce

From this directory:

```sh
python3 run_tokens.py
# Or select the CACTI binary explicitly:
python3 run_tokens.py --cacti /u/rgq5aw/GIT/cacti/cacti
```

The runner copies the configs into a fresh `/tmp/secure-pim-token-cacti.*`
directory, preserving logs, raw outputs, summary and binary provenance there.
It validates returned capacities and output widths and fails if CACTI returns
no model. Reported LOC cycles use `--clock-ns 0.333` by default. The runner does
not overwrite the checked-in configs or recorded results.
