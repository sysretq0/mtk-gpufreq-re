# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""Enable ``python -m mtk_gpufreq_re``."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
