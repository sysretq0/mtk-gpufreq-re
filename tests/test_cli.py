# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""End-to-end tests for the command-line interface (run as a subprocess)."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _synth

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
CLI = [sys.executable, "-m", "mtk_gpufreq_re"]
ENV = dict(os.environ, PYTHONPATH=str(SRC) + os.pathsep + os.environ.get("PYTHONPATH", ""))


def run(*args):
    return subprocess.run(CLI + list(args), cwd=REPO, env=ENV, capture_output=True, text=True)


def make_module(path: Path, *, with_symbol: bool = True) -> Path:
    """Write a synthetic module carrying the patch context and a small OPP table."""
    text, _ = _synth.text_with_context()
    table = _synth.opp_bytes(
        [
            (1100000, 900000, 950000, 0, 0, 0),
            (1000000, 850000, 900000, 1, 0, 0),
            (390000, 500000, 550000, 7, 0, 0),
        ]
    )
    symbols = [("g_default_gpu", ".data", 0, len(table))] if with_symbol else []
    path.write_bytes(_synth.build_elf(text=text, data=table, symbols=symbols))
    return path


class VersionTests(unittest.TestCase):
    def test_version_flag(self):
        r = run("--version")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("mtk-gpufreq-re", r.stdout)


class InfoCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = make_module(Path(self.tmp.name) / "mod.ko")

    def test_info_reports_reference_mismatch_and_patch_state(self):
        r = run("info", str(self.mod))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("reference : different", r.stdout)
        self.assertIn("unlock-working-opp-table", r.stdout)

    def test_check_reports_stock(self):
        r = run("check", str(self.mod))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("stock", r.stdout)


class OppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_summary_and_rows(self):
        mod = make_module(self.dir / "mod.ko")
        r = run("opp", str(mod))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("3 entries", r.stdout)
        self.assertIn("fastest 1100000 kHz", r.stdout)
        self.assertIn("[00]", r.stdout)

    def test_quiet_hides_rows(self):
        mod = make_module(self.dir / "mod.ko")
        r = run("opp", str(mod), "-q")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("[00]", r.stdout)

    def test_missing_symbol(self):
        mod = make_module(self.dir / "mod.ko")
        r = run("opp", str(mod), "--symbol", "nope")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("symbol not found", r.stderr)

    def test_module_without_symtab(self):
        mod = make_module(self.dir / "mod.ko", with_symbol=False)
        r = run("opp", str(mod))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no symbol table", r.stderr)


class UnlockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.mod = make_module(self.dir / "mod.ko")

    def test_refuses_non_reference_without_force(self):
        r = run("unlock", str(self.mod))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("reference build", r.stderr)

    def test_force_writes_output_and_only_three_bytes_change(self):
        out = self.dir / "mod.oc.ko"
        r = run("unlock", str(self.mod), "--force", "-o", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("changed  : 3 bytes", r.stdout)
        self.assertTrue(out.exists())

        before = self.mod.read_bytes()
        after = out.read_bytes()
        self.assertEqual(len(before), len(after))
        self.assertEqual(sum(1 for a, b in zip(before, after) if a != b), 3)

        r2 = run("check", str(out))
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("applied", r2.stdout)

    def test_default_output_name(self):
        r = run("unlock", str(self.mod), "--force")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.mod.with_suffix(".oc.ko").exists())


class LimitsTests(unittest.TestCase):
    def test_prints_write_reference(self):
        r = run("limits")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SEGMENT", r.stdout)
        self.assertIn("set 0 7 44", r.stdout)


if __name__ == "__main__":
    unittest.main()
