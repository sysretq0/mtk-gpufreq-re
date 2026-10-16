# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""mtk-gpufreq-re: reverse-engineering and patch toolkit for the MediaTek GPU
DVFS kernel modules.

Public API::

    from mtk_gpufreq_re import elf, opp, patch

    module = elf.Elf64(open("mtk_gpufreq_mt6789.ko", "rb").read())
    patch.apply(module, patch.UNLOCK_WORKING_OPP_TABLE)
    open("mtk_gpufreq_mt6789.oc.ko", "wb").write(module.to_bytes())
"""

from __future__ import annotations

from . import elf, known, opp, patch
from .__about__ import __license__, __summary__, __title__, __version__
from .elf import Elf64, ElfError
from .opp import OPP, parse_table
from .patch import UNLOCK_WORKING_OPP_TABLE, InstructionPatch, PatchError

__all__ = [
    "__title__",
    "__version__",
    "__summary__",
    "__license__",
    "elf",
    "known",
    "opp",
    "patch",
    "Elf64",
    "ElfError",
    "OPP",
    "parse_table",
    "InstructionPatch",
    "PatchError",
    "UNLOCK_WORKING_OPP_TABLE",
]
