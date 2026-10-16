# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""Instruction-level patching of the GPU DVFS module.

A patch is described by the instruction words immediately around the word it
replaces.  The surrounding ``suffix`` is used as the search anchor and must be
unique in the section; the words before the site are re-checked so the patch
cannot land on an unrelated instruction stream.  The site is then validated to
hold either the expected original or the already-patched encoding.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .elf import Elf64

__all__ = [
    "PatchError",
    "InstructionPatch",
    "UNLOCK_WORKING_OPP_TABLE",
    "PATCHES",
    "locate",
    "state",
    "apply",
    "apply_bytes",
]


class PatchError(Exception):
    """Raised when a patch cannot be located or applied."""


@dataclass(frozen=True)
class InstructionPatch:
    """A single 32-bit instruction substitution."""

    key: str
    title: str
    section: str
    prefix: tuple[int, ...]
    suffix: tuple[int, ...]
    old: int
    new: int
    summary: str

    @property
    def context(self) -> tuple[int, ...]:
        """The full instruction window around the substitution."""
        return self.prefix + (self.old,) + self.suffix


# __gpufreq_pdrv_probe, the point where the working-table selection flag is
# folded.  Clearing the flag makes the working table equal signed[0..44].
UNLOCK_WORKING_OPP_TABLE = InstructionPatch(
    key="unlock-working-opp-table",
    title="Unlock the full signed GPU OPP range",
    section=".text",
    prefix=(0x1A9F07E9,),  # cset  w9, ne
    suffix=(0x528004AB, 0x7100011F, 0x1A8A1164),  # mov w11,#0x25 ; cmp w8,#0 ; csel w4,w11,w10,ne
    old=0x2A090108,  # orr   w8, w8, w9
    new=0x2A1F03E8,  # mov   w8, wzr
    summary="orr w8, w8, w9 -> mov w8, wzr; working table becomes signed[0..44]",
)

PATCHES = {UNLOCK_WORKING_OPP_TABLE.key: UNLOCK_WORKING_OPP_TABLE}


def locate(elf: Elf64, patch: InstructionPatch) -> int:
    """Return the section-relative offset of the patched instruction."""
    if not patch.suffix:
        raise PatchError("patch %r has no search anchor" % patch.key)
    needle = struct.pack("<" + "I" * len(patch.suffix), *patch.suffix)
    hits = elf.find(patch.section, needle)
    if len(hits) != 1:
        raise PatchError("expected exactly one site for %r, found %d" % (patch.key, len(hits)))
    site = hits[0] - 4
    if site < 0:
        raise PatchError("patch site precedes section start")

    for back, want in enumerate(reversed(patch.prefix), start=1):
        got = elf.read_u32(patch.section, site - 4 * back)
        if got != want:
            raise PatchError(
                "context mismatch at offset 0x%x: got %#010x, want %#010x"
                % (site - 4 * back, got, want)
            )

    word = elf.read_u32(patch.section, site)
    if word not in (patch.old, patch.new):
        raise PatchError("unexpected instruction at 0x%x: %#010x" % (site, word))
    return site


def state(elf: Elf64, patch: InstructionPatch) -> str:
    """Return ``"absent"``, ``"stock"`` or ``"applied"`` for ``patch``."""
    try:
        site = locate(elf, patch)
    except PatchError:
        return "absent"
    return "applied" if elf.read_u32(patch.section, site) == patch.new else "stock"


def apply(elf: Elf64, patch: InstructionPatch) -> int:
    """Apply ``patch`` in place and return the patched offset."""
    current = state(elf, patch)
    if current == "applied":
        raise PatchError("patch %r is already applied" % patch.key)
    if current != "stock":
        raise PatchError("cannot apply patch %r: site is %s" % (patch.key, current))
    site = locate(elf, patch)
    elf.write_u32(patch.section, site, patch.new)
    return site


def apply_bytes(data: bytes, patch: InstructionPatch) -> bytes:
    """Return a patched copy of ``data``."""
    elf = Elf64(data)
    apply(elf, patch)
    return elf.to_bytes()
