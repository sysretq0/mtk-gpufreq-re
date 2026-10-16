<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# mtk-gpufreq-re

> Reverse-engineering and patch toolkit for the MediaTek GPU DVFS kernel modules.
>
> Maintained by [sysretq0](https://github.com/sysretq0).

MediaTek's GPU DVFS stack is split across two proprietary kernel modules:
`mtk_gpufreq_mt6789.ko`, the platform driver that owns the GPU OPP tables and
drives the GPUEB, and `mtk_gpufreq_wrapper.ko`, the policy layer that exposes
`/proc/gpufreqv2/*`. The signed OPP table carries **45** operating points, but the
driver exposes only the suffix `signed[7..44]` — **38** points — unless the SoC
reports a higher bin.

This project documents the stack and provides tooling to:

* decode the signed and working OPP tables from the module;
* lift the working table to the full signed range with a single, guarded
  **3-byte** instruction patch;
* control the resulting overclock ceiling through the live limiter interface.

The reverse-engineering that backs the tooling — symbol offsets, the
working-table selector, and the registered function-pointer tables — is recorded
in [`docs/`](docs/) and [`reverse/`](reverse/).

## Features

- ELF64 reader/writer for `ET_REL` kernel modules, standard library only.
- OPP table decoder (`g_default_gpu` and any other named table).
- Anchored instruction patcher: unique suffix anchor, verified prefix context,
  and a `stock`/`applied`/`absent` state machine.
- Reference-build guard (sha256) with an explicit `--force` override.
- Limiter/overclock-cap reference for `/proc/gpufreqv2/limit_table`.
- Stdlib `unittest` suite that builds its own synthetic ELF fixtures; no vendor
  binary and no third-party runtime dependency.

## Install

Python 3.9 or later, standard library only.

```sh
# from a checkout
python -m pip install .

# or run without installing
PYTHONPATH=src python -m mtk_gpufreq_re --help
```

## Usage

```sh
mtk-gpufreq-re info    mtk_gpufreq_mt6789.ko    # sections, hash, patch state
mtk-gpufreq-re check   mtk_gpufreq_mt6789.ko    # stock | applied | absent
mtk-gpufreq-re opp     mtk_gpufreq_mt6789.ko    # decode g_default_gpu
mtk-gpufreq-re unlock  mtk_gpufreq_mt6789.ko    # write mtk_gpufreq_mt6789.oc.ko
mtk-gpufreq-re limits                            # overclock-cap reference
```

Typical `unlock` output:

```
patch    : unlock-working-opp-table
site     : .text offset 0x7c68
stock    : mtk_gpufreq_mt6789.ko  sha256 8837c4f3…18207b89
output   : mtk_gpufreq_mt6789.oc.ko  sha256 c6f35102…3cc6d9a
changed  : 3 bytes
effect   : orr w8, w8, w9 -> mov w8, wzr; working table becomes signed[0..44]
```

## Patching and the overclock cap

The unlock forces the working-table selector to zero, so the working table
becomes `signed[0..44]` (45 entries) instead of `signed[7..44]` (38). It is a
3-byte, in-place change to `__gpufreq_pdrv_probe`; the driver rebuilds and
re-scans the table at probe time, so no other data needs touching. See
[docs/patching.md](docs/patching.md) for the instruction window, the guards and
the reboot/rollback procedure.

`gpufreq` cannot be hot-swapped: the patched module takes effect after a reboot,
so keep a stock copy for rollback.

Once unlocked, cap the top end through the SEGMENT limiter rather than editing
the table:

```sh
echo 'set 0 7 44' > /proc/gpufreqv2/limit_table   # keep the stock maximum (index 7)
echo 'set 0 0 44' > /proc/gpufreqv2/limit_table   # allow the full unlocked range
```

Index `0` is the fastest OPP, so the `ceiling` argument is the overclock limit.
See [docs/limiters.md](docs/limiters.md).

> The unlock exposes OPPs the vendor's binning did not certify for every part.
> The silicon may be unstable at the fastest points. The platform module alone
> carries the change: the wrapper delegates all table and limiter access to it,
> as shown in [docs/architecture.md](docs/architecture.md#delegation).

## Documentation

* [docs/index.md](docs/index.md) — index and reading order.
* [docs/architecture.md](docs/architecture.md) — modules, registration, delegation.
* [docs/opp-tables.md](docs/opp-tables.md) — signed/working tables and layout.
* [docs/patching.md](docs/patching.md) — the unlock, guards, rollback.
* [docs/limiters.md](docs/limiters.md) — the overclock-cap interface.
* [docs/reverse-engineering.md](docs/reverse-engineering.md) — method, evidence,
  open questions.
* [reverse/](reverse/) — symbol table, function-pointer tables and disassembly.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE) and [NOTICE](NOTICE). No vendor
binaries are distributed; see `NOTICE` for the third-party notice.
