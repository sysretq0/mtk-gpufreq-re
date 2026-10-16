<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# mtk-gpufreq-re documentation

This directory documents MediaTek's GPU DVFS kernel stack and how this toolkit
inspects and patches it.

## Reading order

1. **[architecture.md](architecture.md)** — the two modules, how they register and
   who owns what.
2. **[opp-tables.md](opp-tables.md)** — the signed and working OPP tables and their
   layout.
3. **[patching.md](patching.md)** — the single-instruction unlock, its guards and
   its rollback.
4. **[limiters.md](limiters.md)** — the `/proc/gpufreqv2/limit_table` interface that
   controls the overclock ceiling.
5. **[reverse-engineering.md](reverse-engineering.md)** — methodology, evidence and
   open questions.

## Summary

* GPU DVFS is split across `mtk_gpufreq_mt6789.ko` (platform: OPP tables, limiter
  storage, `gpuppm_*`) and `mtk_gpufreq_wrapper.ko` (policy/API layer:
  `/proc/gpufreqv2/*`). The wrapper delegates every read and write to the
  platform through registered function-pointer tables.
* The signed OPP table `g_default_gpu` holds **45** operating points. By default
  the driver exposes only `signed[7..44]` — **38** points — because a
  segment/efuse flag (optionally forced from the `max_gpufreq_support_off`
  device-tree property) selects the trimmed table.
* A single 3-byte patch to `__gpufreq_pdrv_probe` clears that flag, so the working
  table becomes `signed[0..44]` and the seven fastest signed OPPs become
  selectable.
* The overclock ceiling is then controlled at run time through the SEGMENT
  limiter in `/proc/gpufreqv2/limit_table`, which the wrapper forwards to the
  platform.
* Because the wrapper owns nothing but the proc nodes and the delegation, the
  platform patch alone is sufficient — see
  [architecture.md](architecture.md#delegation).

## Provenance

Every statement here was derived from the reference modules recorded in
[`../reverse/`](../reverse): symbols resolved with `llvm-nm`, control flow and
data references recovered with `llvm-objdump -dr`, and the registered
function-pointer tables decoded from their ELF relocations.
