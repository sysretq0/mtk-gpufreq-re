# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""Decoding of the GPU OPP tables.

Each entry is six little-endian ``u32`` fields, 24 bytes in total.  The table is
emitted by the driver in descending frequency order; index 0 is the fastest OPP.
``vaging`` is the aging-margin component of the voltage and ``power`` is a
pre-computed power figure (zero in the signed table, populated in the working
table).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .known import OPP_ENTRY_SIZE

__all__ = ["OPP", "parse_table", "format_table", "summarise"]

_OPP_FMT = "<IIIIII"


@dataclass(frozen=True)
class OPP:
    """One operating point."""

    index: int
    freq_khz: int
    volt_uv: int
    vsram_uv: int
    posdiv: int
    vaging_uv: int
    power: int


def parse_table(raw: bytes, entry_size: int = OPP_ENTRY_SIZE) -> list[OPP]:
    """Decode a raw OPP array into a list of :class:`OPP`."""
    if entry_size != OPP_ENTRY_SIZE:
        raise ValueError("unsupported entry size: %d" % entry_size)
    if len(raw) % entry_size:
        raise ValueError("table length %d is not a multiple of %d" % (len(raw), entry_size))
    out = []
    for index in range(len(raw) // entry_size):
        freq, volt, vsram, posdiv, vaging, power = struct.unpack_from(
            _OPP_FMT, raw, index * entry_size
        )
        out.append(OPP(index, freq, volt, vsram, posdiv, vaging, power))
    return out


def format_table(opps: list[OPP]) -> str:
    """Render a table in the same shape the driver's proc node uses."""
    lines = ["[idx] freq(kHz), volt(uV), vsram(uV), posdiv, vaging(uV), power"]
    for o in opps:
        lines.append(
            "[%02d] freq: %d, volt: %d, vsram: %d, posdiv: %d, vaging: %d, power: %d"
            % (o.index, o.freq_khz, o.volt_uv, o.vsram_uv, o.posdiv, o.vaging_uv, o.power)
        )
    return "\n".join(lines)


def summarise(opps: list[OPP]) -> str:
    """One-line summary: count, fastest and slowest operating point."""
    if not opps:
        return "empty table (0 entries)"
    fastest = max(opps, key=lambda o: o.freq_khz)
    slowest = min(opps, key=lambda o: o.freq_khz)
    return "%d entries, fastest %d kHz (index %d), slowest %d kHz (index %d)" % (
        len(opps),
        fastest.freq_khz,
        fastest.index,
        slowest.freq_khz,
        slowest.index,
    )
