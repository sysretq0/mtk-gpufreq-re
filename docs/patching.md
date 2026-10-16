<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Patching the unlock

## The change

The working-table selection flag is folded in `__gpufreq_pdrv_probe` at
`.text+0x7c68`:

```
.text+0x7c64   0x1A9F07E9   cset  w9, ne            ; flag materialised in w9
.text+0x7c68   0x2A090108   orr   w8, w8, w9        ; <- patched
.text+0x7c6c   0x528004AB   mov   w11, #0x25
.text+0x7c70   0x7100011F   cmp   w8, #0x0
.text+0x7c74   0x1A8A1164   csel  w4, w11, w10, ne
```

The patch replaces the `orr` with `mov w8, wzr`, forcing the flag to zero:

| | encoding | mnemonic |
|---|---|---|
| stock | `0x2A090108` | `orr w8, w8, w9` |
| patched | `0x2A1F03E8` | `mov w8, wzr` |

This is a **3-byte** modification (`0x2A090108 ^ 0x2A1F03E8 = 0x001602E0`).

The flag has two sources — a per-SoC segment/efuse bit (`g_gpu.7`,
`.bss+0x120`) and the device-tree property `max_gpufreq_support_off` — which the
`orr` merges. Clearing the merged result neutralises both. Afterwards `start = 0`
and `count = 45`, so the working table is `signed[0..44]`.

## Locating and applying

The patcher never matches a bare address. It searches `.text` for the **suffix**
anchor (`mov/cmp/csel`, three words directly after the site), requires that
anchor to be unique in the section, then re-checks the words *before* the site
(the `prefix`, `cset w9, ne`). Only then is the site accepted, and it must hold
either the stock or the already-patched encoding.

```sh
# report the state without touching anything
mtk-gpufreq-re check  mtk_gpufreq_mt6789.ko     # -> stock | applied | absent

# apply, defaulting the output name to mtk_gpufreq_mt6789.oc.ko
mtk-gpufreq-re unlock mtk_gpufreq_mt6789.ko

# a build other than the reference requires an explicit override
mtk-gpufreq-re unlock some-other.ko --force
```

`unlock` refuses to run on a module whose sha256 does not match the reference
build unless `--force` is given, and refuses to patch an already-patched or
unrecognised site. The `state` machine used by the tooling is:

| state | meaning |
|---|---|
| `absent` | the anchor is not unique, or the site does not hold the expected word |
| `stock` | the site holds `orr w8, w8, w9` — ready to patch |
| `applied` | the site holds `mov w8, wzr` |

## Applying on a device

`gpufreq` is initialised during early boot and cannot be hot-swapped; the
patched module is loaded only after a reboot. The procedure is:

```sh
# 1. keep a stock copy — this is the only rollback for the running boot
adb shell su -c 'cp /vendor/lib/modules/mtk_gpufreq_mt6789.ko /data/local/tmp/stock.ko'

# 2. build the patched module on the host
mtk-gpufreq-re unlock mtk_gpufreq_mt6789.ko
adb push mtk_gpufreq_mt6789.oc.ko /data/local/tmp/

# 3. place it on a writable, verity-free path and reboot
#    (the exact mechanism is device-specific; mount /vendor rw or use an overlay)
```

After reboot, confirm with:

```sh
cat /proc/gpufreqv2/gpu_working_opp_table     # 45 entries
```

## Risk and rollback

* A malformed replacement can prevent the module from loading, leaving the GPU
  without DVFS. Keep the stock `.ko` and a known-good boot path.
* The unlock exposes OPPs the vendor's binning did not certify for the part. The
  silicon may be unstable at the fastest points; use the SEGMENT limiter
  ([limiters.md](limiters.md)) to cap the top end rather than editing the table.
* Rollback: restore the stock module and reboot.
