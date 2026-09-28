# Unified request/execution/completion table (UR)

One bounded LOC structure replaces RC and EQ. Pending commands, synchronous
copies, and completed-unwaited results compete for the same slots. The
analytical controller has no second descriptor/object-reference queue.

| Part | Packed fields (bits) |
|---|---|
| Lookup tag | requestId16 |
| Completion/ownership | completionTick64 + status9 + ownerToken32 |
| Lifecycle | state2: Pending / Consuming / Completed |
| Lifetime references | objectIds[3] = 48 |
| Descriptor | opcode8 + byteLength64 + deviceBases[3] = 264 |
| Total data | 419 bits -> 53 bytes -> CACTI 64-byte line |

Pending includes queued/running. Consuming marks an early wait or synchronous
copy whose record must survive until object references can be released.
Completed records retain status until wait or pressure eviction. No FIFO
head/tail array is required. Object inFlight counters remain in OC/the backing
object directory. IDs zero mark unused references/empty tags; no added valid
bit. ADD_INT32 implies element width and operand roles; object IDs are not
duplicated inside the descriptor. Copies use one ID/base and auto-retire.

Hardware sizing retains the prior TEE16/process16/objectId16/requestId16
proposal. C++ still uses full 64-bit IDs/tokens/status: this is NOT its sizeof
or an implementation of narrow-ID wrap protection. A future functional DMA
engine would also need host-address/translation/buffer information; this
analytical record intentionally does not model an actual DMA protocol.

`ur.cfg`: fully associative CAM+SRAM, 1 search + 1 RW port, one bank, 512-bit
output, 22-nm HP/360 K; other settings match the existing package.

| Entries | Data bytes | Tag bytes | Access ns | Access / 0.333ns | Cycle ns |
|---:|---:|---:|---:|---:|---:|
| 64 (gem5 default capacity) | 4096 | 128 | 0.235893 | 0.708387387 | 0.450583 |
| 256 (ur.cfg, largest passing tested power of two) | 16384 | 512 | 0.330977 | 0.993924925 | 0.450583 |

512 entries fails access at 0.431328 ns; 128 gives no valid model under these
tool settings. Sweep tested 8..8192 entries. 256 has only 2.023 ps of access
margin: not evidence of physical timing closure. Every returned organization
has cycle time above 333 ps: budget at least 2 LOC cycles between accesses on
the same port, even when a single access fits one cycle. CACTI does not supply
separate measured write latency or permission/ownership comparator timing.

Gem5 capacity/timing defaults are unchanged (64 slots, 5-cycle lookup/insert/
update/remove). Raising capacity to 256 requires OC inFlight9 (0..256), still
within OC's padded 32 bytes. CACTI does not model free-slot selection, pending
completion selection, arbitration, or full-table oldest-completed selection.
Those remain control logic / simulator event bookkeeping, not free hardware.

Reproduce: `bash sweep_unified.sh /absolute/path/to/cacti`.
Recorded outputs: `unified_sweep_results.csv`; detailed selected runs:
`ur_64_result.csv`, `ur_256_result.csv`. Old RC/EQ configs are retained only
for comparison; do not sum them with UR when reporting area/energy.
