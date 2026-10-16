<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Reverse-engineering notes

## Method

1. Both modules are unstripped `ET_REL` objects, so `llvm-nm -S` gives every
   symbol with its section-relative value and size. That immediately located the
   OPP tables (`g_default_gpu`, `g_aging_table`, ...) and the accessor functions.
2. `llvm-objdump -dr --no-show-raw-insn` disassembles with in-place relocations,
   which is what makes the code readable: every `.bss`/`.data` reference is
   annotated with a symbol plus offset (e.g. `.bss+0xf8`).
3. To learn which functions the wrapper actually calls, the `R_AARCH64_ABS64`
   relocations of the registered pointer tables were decoded. Each entry points
   at a `.cfi_jt` slot, so the entry's target resolves to a concrete platform
   function such as `__gpufreq_get_opp_num_gpu`.
4. The patch site was found by following the value that selects the working-table
   slice from `__gpufreq_pdrv_probe` to the instruction that folds it.

Because the objects are `ET_REL`, section addresses are zero and the disassembler
prints section-relative offsets. All offsets quoted in this repository follow
that convention.

## Reference facts

| item | value |
|---|---|
| module | `mtk_gpufreq_mt6789.ko` |
| size / sha256 | 196672 bytes / `8837c4f3…18207b89` |
| vermagic | `5.10.237-android12-9-g5ae907723135 SMP preempt mod_unload modversions aarch64` |
| `.text` | file offset `0x1000`, size `0x9018` |
| `.data` | file offset `0xb778`, size `0x1538` |
| `.rodata` | file offset `0xccb0` |
| symbols | `.symtab`/`.strtab` present (unstripped) |

`CONFIG_MODULE_SIG` is not set on the reference kernel
(`modules_disabled=0`, `MODVERSIONS=y`), so an in-place data/flag patch keeps the
`__versions` CRCs valid and needs no signature.

## Recovered layout

| symbol | section offset | size | note |
|---|---|---|---|
| `g_default_gpu` | `.data+0x598` | `0x438` | 45 signed OPPs |
| `g_aging_table` | `.data+0x9d0` | `0x2d0` | 45 × 16 |
| `g_gpu_limit_table` | `.data+0x1e4` | `0x1e4` | limiter table |
| `platform_ap_fp.46` | `.data+0xca0` | `0x1e0` | GPU accessor fp table |
| `platform_ap_fp` | `.data+0x3f8` | `0x48` | gpuppm fp table |

Key fields in `g_gpu` (`.bss`):

| field | offset | meaning |
|---|---|---|
| `g_gpu.7` | `0x120` | segment/efuse flag merged into the table selector |
| `g_gpu.1` | `0xe0` | working-table pointer |
| `g_gpu.11` | `0xf8` | working-table count (38 stock, 45 unlocked) |
| `g_gpu.0` | `0x108` | signed-table pointer |
| `g_gpu.9` | `0x5c0` | working-table start offset |

## Open questions

* The `.data` section is emitted as one object named `.rela.data.gpuppm_lock` in
  the relocation table, i.e. it is a linker group whose signature comes from
  `gpuppm_lock`; the individual variable offsets above were recovered from the
  relocations themselves, not from separate section names.
* `gpueb-support` selects a parallel `platform_eb_fp.47` table and an IPI path
  (`gpufreq_ipi_to_gpueb`). The devices analysed here leave it disabled, so the
  kernel-side path documented here is the active one.
* `max_gpufreq_support_off` is a second, device-tree-controlled source for the
  same selector; clearing the merged flag covers both, but the property's intended
  use in stock firmware is not fully traced.
