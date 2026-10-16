<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Architecture

MediaTek's GPU DVFS is implemented by two cooperating kernel modules plus the
on-SoC GPUEB microcontroller.

| component | role |
|---|---|
| `mtk_gpufreq_mt6789.ko` | **Platform driver.** Owns the OPP tables, builds the working table, stores and enforces the limiter table, and drives frequency/voltage commits. Implements the `gpuppm_*` (power/performance management) and `__gpufreq_*_gpu` accessors. |
| `mtk_gpufreq_wrapper.ko` | **Policy / API layer.** Creates the `/proc/gpufreqv2/*` nodes and provides the exported `gpufreq_*` API to other kernel clients (thermal, powerhal-facing paths). Delegates all state to the platform driver. |
| GPUEB | The GPU energy-management coprocessor. When enabled (`gpueb-support`) the actual DVFS decisions are made there; on the devices analysed here the property is absent, so the kernel-side path is used. |

The whole stack is exposed to userspace under `/proc/gpufreqv2/`:

| node | contents |
|---|---|
| `gpu_signed_opp_table` | The 45-entry signed table. |
| `gpu_working_opp_table` | The table currently in effect (38 entries stock, 45 after the unlock). |
| `limit_table` | The limiter table; writable to cap/floor the selectable OPP range. |
| `gpufreq_status` | Current index, frequency, voltage. |

## Registration

During `__gpufreq_pdrv_probe` the platform driver:

1. reads its device-tree properties (`aging-load`, `mcl50-load`,
   `max_gpufreq_support_off`, `gpueb-support`);
2. builds the working OPP table from the signed table;
3. calls `gpufreq_register_gpufreq_fp(&platform_ap_fp.46)`, handing the wrapper the
   table of GPU accessor functions;
4. calls `gpuppm_init(...)`, which calls
   `gpufreq_register_gpuppm_fp(&platform_ap_fp)`, handing the wrapper the limiter
   back-end.

The wrapper stores the two pointers in its own `.bss`:

```
mtk_gpufreq_wrapper.ko  .bss gpufreq_fp (0x00) <- &platform_ap_fp.46
mtk_gpufreq_wrapper.ko  .bss gpuppm_fp  (0x30) <- &platform_ap_fp
```

## Delegation

Every wrapper getter/setter dereferences the stored table and calls into the
platform. The relevant entries are:

| wrapper function | table | entry | platform function |
|---|---|---|---|
| `gpufreq_get_working_table` | `gpufreq_fp` | `+0xf8` | `__gpufreq_get_working_table_gpu` |
| `gpufreq_get_signed_table` | `gpufreq_fp` | `+0x100` | `__gpufreq_get_signed_table_gpu` |
| `gpufreq_get_opp_num` | `gpufreq_fp` | `+0xc0` | `__gpufreq_get_opp_num_gpu` |
| `gpufreq_get_debug_opp_info` | `gpufreq_fp` | `+0x108` | `__gpufreq_get_debug_opp_info_gpu` |
| `gpufreq_set_limit` | `gpuppm_fp` | `+0x08` | `gpuppm_set_limit` |
| `gpufreq_switch_limit` | `gpuppm_fp` | `+0x10` | `gpuppm_switch_limit` |
| `gpufreq_get_limit_table` | `gpuppm_fp` | `+0x38` | `gpuppm_get_limit_table` |

The full tables are recorded in
[`../reverse/fp-tables.tsv`](../reverse/fp-tables.tsv).

The consequence for this project is that the wrapper is **not** an independent
limiter or table store. It returns the platform's current table pointer and
count, and forwards limiter writes to `gpuppm_set_limit`. A change made in the
platform module alone therefore propagates to the proc interface.

### The one cached value

`gpu_working_opp_table_proc_show` iterates a count held in
`wrapper.bss+0x58`, and that word is written only once, by
`gpufreq_debug_init` (called from `gpufreq_register_gpuppm_fp` during the
platform probe). It is copied from `__gpufreq_get_debug_opp_info_gpu`, field
`+0x34`, which is the platform's **live** working count (`g_gpu.11`,
`.bss+0xf8`). It is not a compile-time constant and it is captured after the
working table has been built, so it tracks the platform automatically.

On the reference device both the listing and the default SEGMENT floor already
reflect the live count (38 entries, floor 37 = count − 1), which confirms the
capture happens after the table is built. After the unlock they become 45 and 44.
