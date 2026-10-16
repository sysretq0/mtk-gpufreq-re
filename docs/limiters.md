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

* `set` changes the bounds: `ceiling` is the fastest index allowed, `floor` the
  slowest.
* `switch` enables/disables the ceiling and floor contributions of the limiter
  (`c_enable`, `f_enable`).

Index `0` is the fastest OPP, so **`ceiling` selects the overclock limit**:
a smaller ceiling excludes the fastest points.

## Limiter identifiers

| id | name |
|---|---|
| 0 | SEGMENT |
| 1 | DEBUG |
| 2 | THERMAL_AP |
| 3 | THERMAL_EB |
| 4 | SRAMRC |
| 5 | BATT_OC |
| 6 | BATT_PERCENT |
| 7 | LOW_BATT |
| 8 | PBM |
| 9 | APIBOOST |
| 10 | FPSGO |

`SEGMENT` is the per-SoC adjustment limiter. On the reference device it is
initialised by `gpuppm_init` to `ceiling = 0`, `floor = count − 1` (i.e. the whole
working range). After the unlock that is `ceiling = 0`, `floor = 44` — every signed
OPP is reachable.

`mtk-gpufreq-re limits` prints the format above together with the identifier
table, and reads nothing from the device.

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
valid index (`count − 1`), which is `count` from
`/proc/gpufreqv2/gpu_working_opp_table`.

Because these bounds live in the platform module and are applied by
`gpuppm_set_limit`, the cap takes effect through the wrapper without any module
change; see [architecture.md](architecture.md#delegation).
