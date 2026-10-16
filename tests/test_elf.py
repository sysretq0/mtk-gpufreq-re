# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""Tests for the minimal ELF64 reader/writer."""

from __future__ import annotations

import hashlib
import struct
import unittest

import _synth

from mtk_gpufreq_re.elf import Elf64, ElfError


class RejectTests(unittest.TestCase):
    def test_rejects_short_blob(self):
        with self.assertRaises(ElfError):
            Elf64(b"\x7fELF")

    def test_rejects_non_elf_magic(self):
        with self.assertRaises(ElfError):
            Elf64(b"MZ" + b"\x00" * 62)

    def test_rejects_32_bit(self):
        data = bytearray(_synth.build_elf(text=b"\x00" * 8))
        data[4] = 1
        with self.assertRaises(ElfError):
            Elf64(bytes(data))

    def test_rejects_big_endian(self):
        data = bytearray(_synth.build_elf(text=b"\x00" * 8))
        data[5] = 2
        with self.assertRaises(ElfError):
            Elf64(bytes(data))


class SectionTests(unittest.TestCase):
    def test_named_sections_present(self):
        elf = Elf64(_synth.build_elf(text=b"\x11" * 8, data=b"\x22" * 8, rodata=b"\x33" * 8))
        for name in (".text", ".data", ".rodata"):
            with self.subTest(name=name):
                self.assertTrue(elf.has_section(name))
        self.assertFalse(elf.has_section(".bss"))

    def test_missing_section_raises(self):
        elf = Elf64(_synth.build_elf(text=b"\x11" * 8))
        with self.assertRaises(ElfError):
            elf.section(".bss")

    def test_section_data_window(self):
        elf = Elf64(_synth.build_elf(text=b"\x11" * 8))
        self.assertEqual(elf.section_data(".text"), b"\x11" * 8)

    def test_sections_accessor_is_a_copy(self):
        elf = Elf64(_synth.build_elf(text=b"\x11" * 8))
        got = elf.sections
        got.clear()
        self.assertTrue(any(s.name == ".text" for s in elf.sections))


class WordAccessTests(unittest.TestCase):
    def test_read_write_roundtrip(self):
        elf = Elf64(_synth.build_elf(text=b"\x00" * 16))
        elf.write_u32(".text", 4, 0xDEADBEEF)
        self.assertEqual(elf.read_u32(".text", 4), 0xDEADBEEF)

    def test_write_masks_to_32_bits(self):
        elf = Elf64(_synth.build_elf(text=b"\x00" * 4))
        elf.write_u32(".text", 0, 0x100000005)
        self.assertEqual(elf.read_u32(".text", 0), 5)

    def test_read_out_of_range(self):
        elf = Elf64(_synth.build_elf(text=b"\x00" * 4))
        with self.assertRaises(ElfError):
            elf.read_u32(".text", 4)

    def test_write_out_of_range(self):
        elf = Elf64(_synth.build_elf(text=b"\x00" * 4))
        with self.assertRaises(ElfError):
            elf.write_u32(".text", 2, 1)


class FindTests(unittest.TestCase):
    def test_finds_every_occurrence(self):
        words = _synth.pack_words([0x11111111, 0x22222222, 0x11111111, 0x22222222])
        elf = Elf64(_synth.build_elf(text=words))
        needle = struct.pack("<I", 0x11111111)
        self.assertEqual(elf.find(".text", needle), [0, 8])

    def test_no_match(self):
        elf = Elf64(_synth.build_elf(text=b"\x00" * 8))
        self.assertEqual(elf.find(".text", b"\x99\x99\x99\x99"), [])


class SymbolTests(unittest.TestCase):
    def test_absent_symbol_table(self):
        elf = Elf64(_synth.build_elf(text=b"\x00" * 8))
        self.assertEqual(elf.symbols(), {})

    def test_symbol_resolution(self):
        table = _synth.opp_bytes([(1000, 800000, 900000, 7, 10, 20)])
        elf = Elf64(
            _synth.build_elf(
                data=table,
                symbols=[("g_default_gpu", ".data", 0, len(table))],
            )
        )
        syms = elf.symbols()
        self.assertIn("g_default_gpu", syms)
        sym = syms["g_default_gpu"]
        self.assertEqual(sym.section, ".data")
        self.assertEqual(sym.value, 0)
        self.assertEqual(sym.size, len(table))


class SerialisationTests(unittest.TestCase):
    def test_roundtrip(self):
        data = _synth.build_elf(text=b"\x01" * 8)
        self.assertEqual(Elf64(data).to_bytes(), data)

    def test_sha256_tracks_mutation(self):
        data = _synth.build_elf(text=b"\x01" * 8)
        elf = Elf64(data)
        before = hashlib.sha256(data).hexdigest()
        self.assertEqual(elf.sha256(), before)
        elf.write_u32(".text", 0, 0)
        self.assertNotEqual(elf.sha256(), before)


if __name__ == "__main__":
    unittest.main()
