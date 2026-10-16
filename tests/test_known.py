# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""Guard rails for the reverse-engineering registry in :mod:`mtk_gpufreq_re.known`."""

from __future__ import annotations

import unittest

from mtk_gpufreq_re import known


class ReferenceModuleTests(unittest.TestCase):
    def test_filename_and_vermagic(self):
        ref = known.REFERENCE_MODULE
        self.assertEqual(ref["filename"], "mtk_gpufreq_mt6789.ko")
        self.assertIn("modversions", ref["vermagic"])
        self.assertIn("5.10.237", ref["vermagic"])

    def test_sha256_is_a_digest(self):
        digest = known.REFERENCE_MODULE["sha256"]
        self.assertEqual(len(digest), 64)
        int(digest, 16)  # must be hexadecimal


class TableGeometryTests(unittest.TestCase):
    def test_working_is_a_suffix_of_signed(self):
        self.assertEqual(
            known.WORKING_OPP_COUNT + known.WORKING_OPP_START,
            known.SIGNED_OPP_COUNT,
        )

    def test_signed_table_size_matches_count(self):
        table = known.OPP_TABLE_SYMBOLS["g_default_gpu"]
        self.assertEqual(table["size"], known.SIGNED_OPP_COUNT * known.OPP_ENTRY_SIZE)

    def test_aging_table_covers_signed_range(self):
        aging = known.ADJUSTMENT_SYMBOLS["g_aging_table"]
        self.assertGreaterEqual(aging["size"] // 16, known.SIGNED_OPP_COUNT)

    def test_limit_table_is_distinct_from_signed_table(self):
        self.assertNotEqual(
            known.ADJUSTMENT_SYMBOLS["g_gpu_limit_table"]["offset"],
            known.OPP_TABLE_SYMBOLS["g_default_gpu"]["offset"],
        )


class UnlockSiteTests(unittest.TestCase):
    def test_site_is_recorded(self):
        self.assertEqual(known.UNLOCK_SITE_OFFSET, {"section": ".text", "offset": 0x7C68})


class LimiterTests(unittest.TestCase):
    def test_segment_is_zero_and_ids_are_unique(self):
        self.assertEqual(known.LIMITER_IDS["SEGMENT"], 0)
        self.assertEqual(len(set(known.LIMITER_IDS.values())), len(known.LIMITER_IDS))

    def test_help_documents_write_format_and_examples(self):
        self.assertIn("set    <limiter> <ceiling> <floor>", known.LIMIT_WRITE_HELP)
        self.assertIn("switch <limiter> <c_enable> <f_enable>", known.LIMIT_WRITE_HELP)
        self.assertIn("set 0 7 44", known.LIMIT_WRITE_HELP)

    def test_proc_dir(self):
        self.assertEqual(known.PROC_DIR, "/proc/gpufreqv2")


if __name__ == "__main__":
    unittest.main()
