# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""Tests for OPP table decoding and formatting."""

from __future__ import annotations

import unittest

import _synth

from mtk_gpufreq_re import opp
from mtk_gpufreq_re.known import OPP_ENTRY_SIZE
from mtk_gpufreq_re.opp import OPP


class ParseTests(unittest.TestCase):
    def test_entry_size_constant(self):
        self.assertEqual(OPP_ENTRY_SIZE, 24)

    def test_parses_in_order(self):
        raw = _synth.opp_bytes(
            [
                (1000, 800000, 900000, 7, 10, 20),
                (500, 700000, 800000, 3, 4, 5),
            ]
        )
        entries = opp.parse_table(raw)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], OPP(0, 1000, 800000, 900000, 7, 10, 20))
        self.assertEqual(entries[1], OPP(1, 500, 700000, 800000, 3, 4, 5))

    def test_empty_table(self):
        self.assertEqual(opp.parse_table(b""), [])

    def test_length_not_multiple_raises(self):
        with self.assertRaises(ValueError):
            opp.parse_table(b"\x00" * (OPP_ENTRY_SIZE - 1))

    def test_unsupported_entry_size_raises(self):
        with self.assertRaises(ValueError):
            opp.parse_table(b"\x00" * OPP_ENTRY_SIZE, entry_size=16)


class FormatTests(unittest.TestCase):
    def test_format_has_header_and_rows(self):
        entries = opp.parse_table(_synth.opp_bytes([(1000, 800000, 900000, 7, 10, 20)]))
        text = opp.format_table(entries)
        self.assertIn("freq(kHz)", text)
        self.assertIn("[00] freq: 1000, volt: 800000", text)

    def test_summarise_reports_extremes(self):
        entries = opp.parse_table(
            _synth.opp_bytes(
                [
                    (1000, 0, 0, 0, 0, 0),
                    (500, 0, 0, 0, 0, 0),
                    (750, 0, 0, 0, 0, 0),
                ]
            )
        )
        summary = opp.summarise(entries)
        self.assertIn("3 entries", summary)
        self.assertIn("fastest 1000 kHz (index 0)", summary)
        self.assertIn("slowest 500 kHz (index 1)", summary)

    def test_summarise_empty(self):
        self.assertEqual(opp.summarise([]), "empty table (0 entries)")


if __name__ == "__main__":
    unittest.main()
