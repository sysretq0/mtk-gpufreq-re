# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""Command-line interface for mtk-gpufreq-re."""

from __future__ import annotations

import argparse
import sys

from . import known
from . import opp as opp_mod
from . import patch as patch_mod
from .__about__ import __version__
from .elf import Elf64, ElfError
from .patch import PATCHES, PatchError


def _load_module(path: str) -> tuple[Elf64, bytes]:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise SystemExit("cannot read %s: %s" % (path, exc)) from None
    try:
        return Elf64(data), data
    except ElfError as exc:
        raise SystemExit("%s: %s" % (path, exc)) from None


def _select_patch(key: str) -> patch_mod.InstructionPatch:
    try:
        return PATCHES[key]
    except KeyError:
        raise SystemExit(
            "unknown patch: %s (known: %s)" % (key, ", ".join(sorted(PATCHES)))
        ) from None


def _default_output(path: str) -> str:
    return path[:-3] + ".oc.ko" if path.endswith(".ko") else path + ".oc"


def cmd_info(args: argparse.Namespace) -> int:
    elf, data = _load_module(args.module)
    sha = elf.sha256()
    print("file      : %s" % args.module)
    print("size      : %d bytes" % len(data))
    print("sha256    : %s" % sha)
    print("reference : %s" % ("match" if sha == known.REFERENCE_MODULE["sha256"] else "different"))
    print("patches   :")
    for patch in PATCHES.values():
        print("  %-26s %s" % (patch.key, patch_mod.state(elf, patch)))
    print("sections  :")
    for sec in elf.sections:
        if sec.name:
            print("  %-20s off=0x%06x size=0x%06x" % (sec.name, sec.offset, sec.size))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    elf, _data = _load_module(args.module)
    patch = _select_patch(args.key)
    current = patch_mod.state(elf, patch)
    print("%s: %s" % (patch.key, current))
    if current != "absent":
        site = patch_mod.locate(elf, patch)
        print("  %s offset: 0x%x" % (patch.section, site))
    return 0


def cmd_unlock(args: argparse.Namespace) -> int:
    elf, data = _load_module(args.module)
    patch = _select_patch(args.key)

    sha = elf.sha256()
    if sha != known.REFERENCE_MODULE["sha256"] and not args.force:
        raise SystemExit(
            "module does not match the reference build (sha256 %s)\n"
            "pass --force to patch a different build" % sha
        )

    try:
        site = patch_mod.apply(elf, patch)
    except PatchError as exc:
        raise SystemExit(str(exc)) from None

    out = args.output or _default_output(args.module)
    patched = elf.to_bytes()
    with open(out, "wb") as fh:
        fh.write(patched)

    changed = sum(1 for a, b in zip(data, patched) if a != b)
    print("patch    : %s" % patch.key)
    print("site     : %s offset 0x%x" % (patch.section, site))
    print("stock    : %s  sha256 %s" % (args.module, sha))
    print("output   : %s  sha256 %s" % (out, elf.sha256()))
    print("changed  : %d bytes" % changed)
    print("effect   : %s" % patch.summary)
    return 0


def cmd_opp(args: argparse.Namespace) -> int:
    elf, _data = _load_module(args.module)
    symbols = elf.symbols()
    if not symbols:
        raise SystemExit("%s: no symbol table (.symtab) present" % args.module)
    sym = symbols.get(args.symbol)
    if sym is None:
        raise SystemExit("symbol not found: %s" % args.symbol)
    if sym.section is None or sym.size == 0:
        raise SystemExit("symbol %s has no size or section" % args.symbol)

    raw = elf.section_data(sym.section)[sym.value : sym.value + sym.size]
    try:
        entries = opp_mod.parse_table(raw)
    except ValueError as exc:
        raise SystemExit("cannot decode %s: %s" % (args.symbol, exc)) from None

    print("%s (%s +0x%x, %d bytes)" % (args.symbol, sym.section, sym.value, sym.size))
    print(opp_mod.summarise(entries))
    if not args.quiet:
        print(opp_mod.format_table(entries))
    return 0


def cmd_limits(args: argparse.Namespace) -> int:
    print(known.LIMIT_WRITE_HELP)
    print("limiter identifiers:")
    for name, idx in sorted(known.LIMITER_IDS.items(), key=lambda kv: kv[1]):
        print("  %2d  %s" % (idx, name))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mtk-gpufreq-re",
        description="Reverse-engineering and patch toolkit for the MediaTek GPU DVFS kernel modules.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="summarise a module and its patch status")
    p_info.add_argument("module")
    p_info.set_defaults(func=cmd_info)

    p_check = sub.add_parser("check", help="report whether a patch can be located")
    p_check.add_argument("module")
    p_check.add_argument("--key", default=patch_mod.UNLOCK_WORKING_OPP_TABLE.key)
    p_check.set_defaults(func=cmd_check)

    p_unlock = sub.add_parser("unlock", help="apply the OPP unlock patch")
    p_unlock.add_argument("module")
    p_unlock.add_argument("-o", "--output")
    p_unlock.add_argument("--key", default=patch_mod.UNLOCK_WORKING_OPP_TABLE.key)
    p_unlock.add_argument("--force", action="store_true", help="patch a non-reference build")
    p_unlock.set_defaults(func=cmd_unlock)

    p_opp = sub.add_parser("opp", help="decode an OPP table from a symbol")
    p_opp.add_argument("module")
    p_opp.add_argument("--symbol", default="g_default_gpu")
    p_opp.add_argument("-q", "--quiet", action="store_true", help="summary only")
    p_opp.set_defaults(func=cmd_opp)

    p_limits = sub.add_parser("limits", help="print the overclock-limit control reference")
    p_limits.set_defaults(func=cmd_limits)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
