<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Limiters and the overclock cap

The selectable frequency range is not fixed by the OPP table alone: a stack of
*limiters* can each cap the ceiling (fastest allowed OPP) and raise the floor
(slowest allowed OPP). The combined result is what the governor may pick from.

The limiter table lives in the platform module (`g_gpu_limit_table`, `.data+0x1e4`)
and is exposed read-write through:

```
/proc/gpufreqv2/limit_table
```

The wrapper's `limit_table_proc_write` parses the request and forwards it to the
platform's `gpuppm_set_limit` via the `gpuppm_fp` table; the platform performs the
clamping and stores the result.

## Write format

```
set    <limiter> <ceiling> <floor>
switch <limiter> <c_enable> <f_enable>
```

* `set` changes the bounds: the GPU may then use OPP indices in the inclusive
  range `[ceiling, floor]`.
* `switch` enables/disables the ceiling and floor contributions of the limiter
  (`c_enable`, `f_enable`).

Index `0` is the fastest OPP and `count - 1` the slowest, so **`ceiling` selects
the overclock limit**: a larger ceiling excludes the fastest points, and the
working range is the default `[0, count - 1]`.

## Limiter identifiers

The priority column is fixed in the platform module and breaks ties when the
ceiling and floor cross; it is shown in the live table.

| id | name | priority |
|---|---|---|
| 0 | SEGMENT | 9 |
| 1 | DEBUG | 8 |
| 2 | THERMAL_AP | 7 |
| 3 | THERMAL_EB | 7 |
| 4 | SRAMRC | 6 |
| 5 | BATT_OC | 5 |
| 6 | BATT_PERCENT | 5 |
| 7 | LOW_BATT | 5 |
| 8 | PBM | 5 |
| 9 | APIBOOST | 4 |
| 10 | FPSGO | 4 |

`SEGMENT` is the per-SoC adjustment limiter. On the reference device it is
initialised by `gpuppm_init` to `ceiling = 0`, `floor = count - 1` (i.e. the
whole working range). After the unlock that is `ceiling = 0`, `floor = 44` —
every signed OPP is reachable.

`mtk-gpufreq-re limits` prints the format above together with the identifier
table, and reads nothing from the device.

## How the bounds combine

`__gpuppm_sort_limit` reduces every enabled limiter to a single range:

* the effective `ceiling` is the **largest** enabled ceiling that is neither the
  default nor `0` (the most restrictive fastest point); if none qualifies it
  falls back to `SEGMENT`.
* the effective `floor` is the **smallest** enabled floor that is neither the
  default nor `count - 1` (the most restrictive slowest point); if none qualifies
  it falls back to `SEGMENT`.

A ceiling of `0` and a floor of `count - 1` are treated as "no constraint". If
the bounds cross (`ceiling > floor`) `__gpuppm_sort_limit` aligns them using the
priority column: the higher-priority side wins.

## Who drives each limiter

Only the platform module owns the table; the components below call
`gpufreq_set_limit` / `gpufreq_set_limit_by_power` through the wrapper.

| limiter | driven by | when |
|---|---|---|
| SEGMENT | `gpuppm_init` (platform probe) | once, from the live working count |
| DEBUG | `/proc/gpufreqv2/limit_table` | manual debug writes |
| THERMAL_AP | `ap_thermal_limit.c`, Mali GPU devfreq governor | thermal throttling |
| THERMAL_EB | GPU EB thermal | EB-side thermal |
| SRAMRC | `ssc_module.c` | SRAM/RC debug |
| BATT_OC, BATT_PERCENT, LOW_BATT | `mtk_gpu_power_throttling` | battery events |
| PBM | `mtk_pbm` | low-battery power budget |
| APIBOOST, FPSGO | power HAL (userspace) | app/scenario policy |

On the reference device `SEGMENT`, `APIBOOST` and `FPSGO` are the only limiters
carrying a value in normal operation; the rest read `-1` (unset) until their
trigger fires.

The map was cross-checked against the MT6789 kernel source under
`drivers/gpu/mediatek/gpufreq/v2/` (`gpuppm.c`), `drivers/gpu/mediatek/gpu_mali/`,
`drivers/misc/mediatek/{pbm,power_throttling,thermal,ssc}/`, and against the live
`limit_table`.

## Battery and power-budget limiters

`mtk_gpu_power_throttling` reads its per-level caps from the device tree
(`mediatek,gpu-power-throttling`), so they can be read back live from:

```
/sys/firmware/devicetree/base/gpu-power-throttling/{lbat,oc,soc}-{max-level,limit-freq}
```

On MT6789 these levels cap the GPU at `485000` kHz on over-current and on the
deeper low-battery levels; the shallowest level uses `2147483647` (no cap). They
apply only while the corresponding battery event is active.

`mtk_pbm` computes a CPU/GPU power budget and pushes it to the `PBM` limiter,
but only once the battery falls below its threshold. It can be inspected and
overridden from userspace:

```
/proc/pbm/pbm_manual_mode    # echo "manual <0|1|2> <dlpt> <md1> <cpu> <gpu> <flash>"
/proc/pbm/pbm_stop           # echo "stop <0|1|2>"
```

`manual_mode 2` recomputes the split but does not apply it; `pbm_stop 1` stops
the polling and releases the CPU/GPU budget limits. Neither is persistent.

## Interaction with the unlock

On the stock device the working count is `38`, so `gpuppm_init` leaves
`SEGMENT` at `[0, 37]` and the power HAL sets the `APIBOOST` / `FPSGO` values
against that same `37`. After the unlock the working count is `45` and
`gpuppm_init` recomputes `SEGMENT` to `[0, 44]`, but the userspace floors are not
recomputed and keep pointing at index `37`, which is now a mid-table OPP rather
than the slowest one. The effect is small (while a power-HAL limiter is active
the GPU cannot idle to the slowest four OPPs); the top of the range is
unaffected. This is the kernel-side counterpart of the wrapper's single cached
value described in [architecture.md](architecture.md#the-one-cached-value).

## Capping the overclock

Once the working table holds 45 entries, the seven fastest points are indices
`0..6`. To keep the previous stock maximum (index `7`) as the ceiling while
leaving the floor at the slowest point:

```sh
echo 'set 0 7 44' > /proc/gpufreqv2/limit_table
```

To allow the full unlocked range:

```sh
echo 'set 0 0 44' > /proc/gpufreqv2/limit_table
```

Confirm the table size before writing the floor — the floor must be the last
valid index (`count - 1`), which is `count` from
`/proc/gpufreqv2/gpu_working_opp_table`.

Because these bounds live in the platform module and are applied by
`gpuppm_set_limit`, the cap takes effect through the wrapper without any module
change; see [architecture.md](architecture.md#delegation).
