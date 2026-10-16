<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# OPP tables

## Entry layout

Each operating point is six little-endian `u32` fields, 24 bytes in total:

| offset | field | meaning |
|---|---|---|
| `+0x00` | `freq` | frequency in kHz |
| `+0x04` | `volt` | voltage in µV |
| `+0x08` | `vsram` | SRAM voltage in µV |
| `+0x0c` | `posdiv` | post-divider / PLL setting |
| `+0x10` | `vaging` | aging-margin component of the voltage, in µV |
| `+0x14` | `power` | pre-computed power figure (0 in the signed table) |

Entries are emitted in descending frequency order, so index `0` is the fastest
OPP. The `opp` subcommand decodes and prints a table:

```sh
mtk-gpufreq-re opp mtk_gpufreq_mt6789.ko
mtk-gpufreq-re opp mtk_gpufreq_mt6789.ko --symbol g_default_gpu -q
```

## Signed table

| property | value |
|---|---|
| symbol | `g_default_gpu` |
| section | `.data` |
| section-relative offset | `0x598` |
| entries | `45` |
| size | `45 * 24 = 0x438` bytes |

This is the complete, vendor-signed set of operating points. It is a static array
inside the module — not device tree, not a firmware blob — which is why the
unlock can be expressed as a data/flag change rather than a table rewrite.

## Working table

The driver does not use the signed table directly. During
`__gpufreq_pdrv_probe` it allocates a working table and copies a slice of the
signed table into it (descriptor `g_gpu.1`, `.bss+0xe0`), starting at
`g_gpu.9` (`.bss+0x5c0`) with length `g_gpu.11` (`.bss+0xf8`).

Stock, a segment/efuse flag selects the trimmed slice:

```
start = flag ? 7 : 0
count = flag ? 38 : 45
```

so the default working table is `signed[7..44]` (38 points) and the seven
fastest signed OPPs — the ones the binning reserves for higher-graded silicon —
are hidden. Clearing the flag selects `start = 0`, `count = 45`, i.e.
`signed[0..44]`; see [patching.md](patching.md).

## Supporting tables

The working table is not the only per-OPP array that must cover the full range.
The related adjustment tables already span all 45 entries, so no additional
change is required:

| symbol | section offset | size | covering |
|---|---|---|---|
| `g_aging_table` | `0x9d0` | `0x2d0` = 45 × 16 | all 45 OPPs |
| `g_avs_adj` | `0x1060` | `0x3c` | — |
| `g_segment_adj` | `0x109c` | `0x140` | — |
| `g_gpu_limit_table` | `0x1e4` | `0x1e4` | limiter table (see [limiters.md](limiters.md)) |
| `g_core_mask_table` | `0x498` | `0x10` | — |

After the working table is rebuilt, `__gpufreq_init_opp_idx` re-scans it and
recomputes the frequency→index mapping, and the limiter bounds are derived from
the new count, so the extended range is usable without further patching.
