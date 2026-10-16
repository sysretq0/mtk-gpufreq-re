# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""Registry of everything identified while reversing the GPU DVFS modules.

Every constant here is evidence, not configuration.  Offsets are section
relative (the modules are ``ET_REL`` objects); the section is named alongside
each value.  The address and struct layout were recovered from
``mtk_gpufreq_mt6789.ko`` build ``5.10.237-android12-9-g5ae907723135`` and are
recorded in ``docs/reverse-engineering.md``.
"""

from __future__ import annotations

__all__ = [
    "REFERENCE_MODULE",
    "UNLOCK_SITE_OFFSET",
    "OPP_ENTRY_SIZE",
    "SIGNED_OPP_COUNT",
    "WORKING_OPP_COUNT",
    "OPP_TABLE_SYMBOLS",
    "ADJUSTMENT_SYMBOLS",
    "PROBE_GLOBALS",
    "DT_PROPERTIES",
    "LIMITER_IDS",
    "LIMIT_WRITE_HELP",
    "PROC_DIR",
]

# The exact module the patch was derived against.  Used as a guard so the
# patcher refuses a build it has not been verified on unless forced.
REFERENCE_MODULE = {
    "filename": "mtk_gpufreq_mt6789.ko",
    "sha256": "8837c4f33c656eb4c778aec552450ec999b6db8f437717b94872842618207b89",
    "size": 196672,
    "vermagic": "5.10.237-android12-9-g5ae907723135 SMP preempt mod_unload modversions aarch64",
}

# Section-relative offset of the instruction that folds the working-table
# selection flag (see patch.UNLOCK_WORKING_OPP_TABLE).
UNLOCK_SITE_OFFSET = {"section": ".text", "offset": 0x7C68}

# OPP entry: struct of six u32 (freq, volt, vsram, posdiv, vaging, power).
OPP_ENTRY_SIZE = 24

SIGNED_OPP_COUNT = 45
WORKING_OPP_COUNT = 38
WORKING_OPP_START = 7  # the driver drops the 7 fastest signed OPPs by default

# OPP tables (section-relative offsets into .data).
OPP_TABLE_SYMBOLS = {
    "g_default_gpu": {"offset": 0x598, "size": SIGNED_OPP_COUNT * OPP_ENTRY_SIZE},
}

# Per-OPP and per-segment adjustment tables.  The aging table already covers
# all 45 entries, so unlocking the range needs no change here.
ADJUSTMENT_SYMBOLS = {
    "g_aging_table": {"offset": 0x9D0, "size": 0x2D0},
    "g_avs_adj": {"offset": 0x1060, "size": 0x3C},
    "g_segment_adj": {"offset": 0x109C, "size": 0x140},
    "g_gpu_limit_table": {"offset": 0x1E4, "size": 0x1E4},
    "g_core_mask_table": {"offset": 0x498, "size": 0x10},
}

# Anonymous globals in .bss reached by the accessor helpers.
PROBE_GLOBALS = {
    "working_table_ptr": 0xE0,
    "working_count": 0xF8,
    "signed_table_ptr": 0x108,
    "segment_flag": 0x120,  # g_gpu.7
    "table_start_flag": 0x5C0,
}

# Device-tree properties read by __gpufreq_pdrv_probe.
DT_PROPERTIES = {
    "aging-load": "g_aging_load",
    "mcl50-load": "g_mcl50_load",
    "max_gpufreq_support_off": "g_max_freq_off_load",
    "gpueb-support": "g_gpueb_support",
}

# Limiter identifiers in the policy table exposed under /proc/gpufreqv2.
LIMITER_IDS = {
    "SEGMENT": 0,
    "DEBUG": 1,
    "THERMAL_AP": 2,
    "THERMAL_EB": 3,
    "SRAMRC": 4,
    "BATT_OC": 5,
    "BATT_PERCENT": 6,
    "LOW_BATT": 7,
    "PBM": 8,
    "APIBOOST": 9,
    "FPSGO": 10,
}

PROC_DIR = "/proc/gpufreqv2"

LIMIT_WRITE_HELP = """\
/proc/gpufreqv2/limit_table write format:

    set    <limiter> <ceiling> <floor>
    switch <limiter> <c_enable> <f_enable>

Index 0 is the fastest OPP, so <ceiling> selects the fastest index the
governor may use and therefore sets the overclock limit.  Limiter 0 is SEGMENT.

    set 0 0 44   # no overclock cap: allow the fastest unlocked OPP
    set 0 7 44   # cap at the previous stock maximum (index 7)
    set 0 N 44   # cap at index N of the working table

The floor must be the last valid index (OPP count - 1).  On a 45-entry working
table that is 44; confirm the table size via
/proc/gpufreqv2/gpu_working_opp_table before changing it.
"""
