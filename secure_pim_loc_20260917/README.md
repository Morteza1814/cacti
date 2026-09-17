# Secure-PIM LOC arrays — 2026-09-17

Four standalone CACTI configurations; no gem5 code/timing/capacity changes.
This package supersedes the earlier 32-MiB/page-encoded OC and extra-valid-bit
sizing proposals under the gem5 repository's configs/cacti directory.

## Encodings

All numbers below are bits unless stated otherwise. Packed hardware proposals,
not sizeof(C++ structs). TEE16 + process16 = subject/owner token32.

| Array | Type / ports | Entries | Lookup tag | Data fields | Payload -> CACTI entry |
|---|---|---:|---|---|---|
| CC | Fully associative CAM+SRAM; 1 search, 1 RW | 256 | TEE16 + process16 + objectId16 = 48 | permissions6 | 6 -> 1 B |
| RC | Fully associative CAM+SRAM; 1 search, 1 RW | 256 | requestId16 | completionTick64 + status9 + ownerToken32 | 105 -> 16 B |
| OC | Fully associative CAM+SRAM; 1 search, 1 RW | 256 | objectId16 | ownerToken32 + physicalBase64 + logicalSize64 + physicalSize64 + state1 + inFlight7 | 232 -> 32 B |
| EQ | FIFO backed by indexed SRAM; 1 R + 1 W, no search | 64 | None (6-bit row index, not a stored tag) | See below | 581 -> 128 B |

EQ fields follow PimExecutionController::Command / AuthorizedPimDescriptor:
- completionTick64, requestId16, operation8, elementBytes8;
- three operands, each objectId16 + access1 + physicalBase64 + length64 = 145 bits;
- retainedCount2 + three retainedObjectId16 = 50 bits.
Total = 64 + 16 + 8 + 8 + 3*145 + 50 = 581 bits.
The retained list is deliberately preserved: current analytical transfers queue
an empty descriptor but retain one object ID. No vector/deque pointers are stored.
Future sharing of operand lengths/retained IDs could shrink the record, but is
not assumed here. Inactive fields may be zero, including a transfer's request ID.
This is an analytical scheduling record, not a complete real DMA protocol/buffer.

OC base and both lengths are byte-based uint64 ranges. This removes the earlier
32-MiB address-width restriction; allocation alignment remains an independent
policy (currently 4 KiB in gem5). Actual configured device capacity is unchanged.
Status9 preserves codes through 0x106; operation8/elementBytes8 cover current
values (ADD=1, elementBytes=4), with explicit encoding limits for future operations.
inFlight7 covers 0..64 under the current queue-depth bound.

## Valid versus occupied

There is NO new capability-valid field, and no extra tag-valid bit in this package.
A hardware array still must distinguish empty slots from live entries. We use
the reserved objectId=0 (CC/OC) or requestId=0 (RC) as the empty-slot sentinel.
The trusted front end must reject zero-ID lookups. Reset/removal clears the ID;
insertion must publish its nonzero key only after payload is ready. This is a
proposed encoding of software table presence, not a change to gem5's containers.

A separate valid bit/bitmap is another legitimate implementation, but is
unnecessary under this explicit sentinel convention. Earlier estimates included
one conservatively, with extra CACTI rounding; those estimates are superseded.
OC state1 (Valid/Revoking) is different: an occupied object may be revoking.

EQ has no per-slot valid bit. Its contiguous FIFO occupancy is tracked outside
the SRAM by head6 + tail6 + occupancyCount7 (19 register bits). Pointer/control
logic is not included in CACTI. Use clock-domain synchronizers if ever made
asynchronous; this model assumes a single LOC clock domain.

16-bit IDs/tokens are sizing assumptions, not permission to truncate current
64-bit identifiers. Prevent zero/wrap/reuse with outstanding stale handles;
a bounded prototype can fail closed before exhaustion. Generation/epoch fields
would need additional modeled bits. No narrow-ID policy is implemented here.

## CACTI results

At the actual LOC period 333 ps (nominal 3 GHz; one tick = 1 ps):

| Array | Data storage | Tag storage | Access ns | LOC cycles | CACTI cycle ns |
|---|---:|---:|---:|---:|---:|
| CC | 256 B | 1536 B | 0.285007 | 0.855876877 | 0.238506 |
| RC | 4096 B | 512 B | 0.254120 | 0.763123123 | 0.217322 |
| OC | 8192 B | 512 B | 0.277413 | 0.833072072 | 0.269531 |
| EQ | 8192 B | 0 | 0.253432 | 0.761057057 | 0.524196 |

Tag/storage counts exclude replacement state and peripheral circuitry; CACTI
area includes its modeled array periphery. Line sizes are rounded to powers of
two, and output buses are 8/128/256/1024 bits respectively (whole padded entry).

CC/RC/OC use the largest passing tested power-of-two capacities through 8192.
The next size (512) fails access: 0.352724 / 0.350823 / 0.374119 ns.
EQ stays at the implemented 64 entries. An isolated EQ sweep can reach 256
entries at 0.329288 ns, but that is NOT the configured design: raising queue depth
also requires revisiting inFlight width (9 bits for 0..256) and FIFO pointers.

All chosen arrays meet the ACCESS target. EQ's 0.524196-ns CYCLE time exceeds
333 ps: do not claim one new access per LOC cycle per port; budget at least
two LOC cycles between accesses on a port in a simple synchronous integration.
Read and write have distinct ports. The other arrays meet both targets.
These analytical estimates do not establish timing closure or separate write
latency. See summary.csv for area, leakage and search/read/write energies.

All configs use 22-nm HP cells/periphery, 360 K, one bank, UCA, conservative
semi-global wiring, Global_30 signaling, no ECC/power gating. CC/RC/OC use fast
access, EQ normal RAM access. Minimum-delay objective: NONE, weights 100:0:0:0:0;
20% delay deviation avoids the tool's strict zero-deviation rejection.
DDR IO/MemCAD parameters are inherited defaults, not the SRAM's clock or latency.
Their unrelated IO warnings/output are not used.

## Reproduce

Run `bash sweep.sh` inside this directory, or provide an absolute CACTI binary:
`bash sweep.sh /u/rgq5aw/GIT/cacti/cacti`.
The default binary is ../cacti. Runs and raw outputs are preserved under /tmp;
sweep_results.csv is the recorded run. no_model denotes a rejected organization,
not a measured timing failure. A full repeat should reproduce the CSV.
Binary SHA256: 85b98f8f25e6772ae6b5288f881f41b3b1525a1b0b915f15d7243ff8a1d41db7.

## Other costs (not additional capability fields)

Replacement/free-slot bookkeeping, FIFO registers, allocator free-range metadata,
and full-table victim scans are not automatically captured by these payloads.
Their hardware designs must be selected before an honest SRAM/logic estimate.
Backing CT/object-table reads use a separate DRAM/HBM model or fixed-latency
assumption; do not charge on-chip hit latency as their memory latency.
Future real DMA buffers need their own sizing; no payload buffer is modeled here.

Permission check +1/operand, object-state check +1/operand, shape/operation checks
+1/command, bounds +1/copy, ownership +1/grant-free-wait remain illustrative
logic budgets, NOT CACTI results. Existing gem5 latency settings are unchanged;
replace/split existing charges when integrating, rather than double-counting.
