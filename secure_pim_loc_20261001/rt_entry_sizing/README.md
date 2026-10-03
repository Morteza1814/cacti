# Request-table entry sizing, 2026-10-01

This CACTI study compares the original RT encoding with compact CAM+SRAM and
indexed-SRAM alternatives. It changes no gem5 fields, capacities, allocation
scheme or timing parameters. The one-cycle RT requirement remains unresolved
in the implemented controller.

The original model has a 64-bit request-ID tag and a 650-bit payload padded to
128 bytes. For the configured 32-MiB device, the compact payload retains full
64-bit identities and timestamps while narrowing status, operation, byte length
and device addresses. `encoding.json` records the resulting 434-bit payload,
padded to 64 bytes. The indexed alternative puts the full request ID in the row,
giving 498 bits in the same 64-byte entry. These are sizing proposals, not
permission to truncate existing software fields.

## Results

The clock target is 0.333 ns. Access time measures read/search-to-result delay;
port cycle time measures spacing between successive accesses on a port.

| Organization | Entries | Data bytes/entry | Access ns | Port cycle ns |
| --- | ---: | ---: | ---: | ---: |
| Original CAM+SRAM | 1 | 128 | no model | no model |
| Original CAM+SRAM | 64 | 128 | 0.496566 | 1.270890 |
| Original, narrower output | 64 | 128 | 0.496566 | 1.270890 |
| Compact CAM+SRAM | 64 | 64 | 0.303868 | 0.519014 |
| Compact CAM+SRAM | 128 | 64 | no model | no model |
| Compact CAM+SRAM | 256 | 64 | 0.401647 | 0.519014 |
| Original indexed SRAM | 64 | 128 | 0.179514 | 0.350759 |
| Compact indexed SRAM | 64 | 64 | 0.114918 | 0.144325 |

Compact CAM64 meets the read-latency target but cannot accept accesses every LOC
cycle on the modeled port. Compact indexed SRAM64 meets both array targets,
but requires a safe request-ID-to-slot scheme and ID/owner/state validation
outside the SRAM. These external costs are not included in the array estimate.
Changing device capacity requires recalculating and validating compact widths.
A one-entry `no_model` result does not rule out a register implementation.

## Artifacts and reproduction

`results.csv` contains all tested cases; `*.cfg` and successful `*.cfg.out`
files retain the inputs and raw outputs. Per-case `.log` files also retain
CACTI diagnostics, including rejected organizations. `provenance.json` identifies the source
model, CACTI binary hash and case dimensions. Shared technology assumptions are
documented in `../README.md`: 22-nm HP, 360 K,
one bank and one read/write port, with a search port for associative models.

Run a selected case in a temporary directory so CACTI can find its technology
files and does not overwrite the saved output:

```sh
rt_cacti_binary=/absolute/path/to/cacti
rt_cacti_output=$(mktemp -d)
ln -s "$(dirname "$rt_cacti_binary")/tech_params" "$rt_cacti_output/tech_params"
cp secure_pim_loc_20261001/rt_entry_sizing/indexed_compact_64.cfg "$rt_cacti_output/"
(cd "$rt_cacti_output" && "$rt_cacti_binary" -infile indexed_compact_64.cfg)
```

Select another saved `.cfg` to reproduce another row. `no_model` means CACTI
found no organization under these constraints, rather than a measured delay.
