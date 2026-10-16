<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Reverse-engineering evidence

Supporting material for the claims made in [`../docs/`](../docs). Everything here
was derived from the two vendor kernel modules with the GNU/LLVM binutils
(`llvm-nm`, `llvm-objdump -dr`) plus a small amount of ELF relocation parsing.

## Reference build

| field | value |
|---|---|
| module | `mtk_gpufreq_mt6789.ko` |
| size | 196672 bytes |
| sha256 | `8837c4f33c656eb4c778aec552450ec999b6db8f437717b94872842618207b89` |
| vermagic | `5.10.237-android12-9-g5ae907723135 SMP preempt mod_unload modversions aarch64` |

The wrapper analysed alongside it is `mtk_gpufreq_wrapper.ko`. Both are
`ET_REL` objects, so every offset quoted anywhere in this repository is relative
to the start of its own section (`.text` at file offset `0x1000`, `.data` at
`0xb778`), **not** a link-time virtual address.

## Files

| file | contents |
|---|---|
| [`symbols.csv`](symbols.csv) | Curated symbol table: name, kind, section-relative value and size, for both modules. |
| [`fp-tables.tsv`](fp-tables.tsv) | The two registered function-pointer tables resolved entry by entry, with the wrapper's stored copy of each. |
| [`disasm/unlock-site.txt`](disasm/unlock-site.txt) | The instruction window around the patched site, before and after. |

## Reproducing

```sh
# list the functions and data objects of interest
llvm-nm -S --defined-only mtk_gpufreq_mt6789.ko

# disassemble with in-place relocations (needed to resolve function pointers)
llvm-objdump -dr --no-show-raw-insn mtk_gpufreq_mt6789.ko
```

The function-pointer tables are built from `R_AARCH64_ABS64` relocations against
the `.text` section symbol; the addend is the section-relative function address.
Reading them back resolves what the wrapper actually calls at run time.

## Scope

Only what is needed to justify the tooling and the patch is recorded here. No
vendor binary, firmware blob or extracted data is distributed with this project;
see [`../NOTICE`](../NOTICE).
