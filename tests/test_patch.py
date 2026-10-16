# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""Tests for the instruction-level patcher."""

from __future__ import annotations

import struct
import unittest

import _synth

from mtk_gpufreq_re.elf import Elf64
from mtk_gpufreq_re.patch import (
    PATCHES,
    UNLOCK_WORKING_OPP_TABLE,
    PatchError,
    apply,
    apply_bytes,
    locate,
    state,
)

PATCH = UNLOCK_WORKING_OPP_TABLE


def _elf(text: bytes) -> Elf64:
    return Elf64(_synth.build_elf(text=text))


class EncodingTests(unittest.TestCase):
    def test_known_encodings(self):
        self.assertEqual(PATCH.old, 0x2A090108)
        self.assertEqual(PATCH.new, 0x2A1F03E8)

    def test_metadata(self):
        self.assertEqual(PATCH.section, ".text")
        self.assertEqual(PATCH.key, "unlock-working-opp-table")
        self.assertIs(PATCHES[PATCH.key], PATCH)

    def test_context_is_the_five_word_window(self):
        self.assertEqual(len(PATCH.context), 5)
        self.assertEqual(PATCH.context, _synth.PATCH_CONTEXT)


class LocateTests(unittest.TestCase):
    def test_site_offset(self):
        text, site = _synth.text_with_context()
        self.assertEqual(locate(_elf(text), PATCH), site)

    def test_absent_when_context_missing(self):
        elf = _elf(_synth.pack_words([0xD503201F] * 8))
        self.assertEqual(state(elf, PATCH), "absent")
        with self.assertRaises(PatchError):
            locate(elf, PATCH)

    def test_ambiguous_anchor_is_rejected(self):
        text, _ = _synth.text_with_context(copies=2)
        with self.assertRaises(PatchError):
            locate(_elf(text), PATCH)

    def test_context_mismatch_is_rejected(self):
        text, site = _synth.text_with_context()
        bad = bytearray(text)
        bad[site - 4 : site] = struct.pack("<I", 0xFFFFFFFF)
        with self.assertRaises(PatchError):
            locate(_elf(bytes(bad)), PATCH)

    def test_unexpected_instruction_is_absent(self):
        text, site = _synth.text_with_context()
        bad = bytearray(text)
        bad[site : site + 4] = struct.pack("<I", 0x00000000)
        self.assertEqual(state(_elf(bytes(bad)), PATCH), "absent")


class StateTests(unittest.TestCase):
    def test_stock(self):
        text, _ = _synth.text_with_context()
        self.assertEqual(state(_elf(text), PATCH), "stock")

    def test_applied(self):
        text, _ = _synth.text_with_context()
        elf = _elf(text)
        apply(elf, PATCH)
        self.assertEqual(state(elf, PATCH), "applied")


class ApplyTests(unittest.TestCase):
    def test_apply_replaces_one_word(self):
        text, site = _synth.text_with_context()
        elf = _elf(text)
        self.assertEqual(apply(elf, PATCH), site)
        self.assertEqual(elf.read_u32(".text", site), PATCH.new)

    def test_apply_twice_raises(self):
        text, _ = _synth.text_with_context()
        elf = _elf(text)
        apply(elf, PATCH)
        with self.assertRaises(PatchError):
            apply(elf, PATCH)

    def test_apply_on_absent_raises(self):
        elf = _elf(_synth.pack_words([0xD503201F] * 8))
        with self.assertRaises(PatchError):
            apply(elf, PATCH)

    def test_apply_bytes_changes_exactly_three_bytes(self):
        text, _ = _synth.text_with_context()
        stock = _synth.build_elf(text=text)
        patched = apply_bytes(stock, PATCH)
        self.assertEqual(len(stock), len(patched))
        self.assertEqual(sum(1 for a, b in zip(stock, patched) if a != b), 3)
        self.assertEqual(state(Elf64(patched), PATCH), "applied")

    def test_apply_bytes_is_confined_to_the_site(self):
        text, site = _synth.text_with_context()
        stock = _synth.build_elf(text=text)
        patched = apply_bytes(stock, PATCH)
        section = Elf64(stock).section(".text")
        low = section.offset + site
        high = low + 4
        for i, (a, b) in enumerate(zip(stock, patched)):
            if a != b:
                self.assertTrue(low <= i < high, "byte 0x%x changed unexpectedly" % i)


if __name__ == "__main__":
    unittest.main()
