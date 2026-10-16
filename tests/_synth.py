# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""Build minimal little-endian ELF64 objects for the test suite.

The generator produces just enough structure for :class:`mtk_gpufreq_re.elf.Elf64`:
a section table with named sections and, optionally, a ``.symtab``.  No vendor
binary is needed to exercise the package.
"""

from __future__ import annotations

import struct

SHT_PROGBITS = 1
SHT_SYMTAB = 2
SHT_STRTAB = 3

SHF_WRITE = 0x1
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4

STT_OBJECT = 2
_ST_INFO = (1 << 4) | STT_OBJECT  # STB_GLOBAL | STT_OBJECT

_TYPES = {
    ".text": SHT_PROGBITS,
    ".data": SHT_PROGBITS,
    ".rodata": SHT_PROGBITS,
    ".symtab": SHT_SYMTAB,
    ".strtab": SHT_STRTAB,
    ".shstrtab": SHT_STRTAB,
}
_FLAGS = {
    ".text": SHF_ALLOC | SHF_EXECINSTR,
    ".data": SHF_ALLOC | SHF_WRITE,
    ".rodata": SHF_ALLOC,
}
_SECTION_INDEX = {"": 0, ".text": 1, ".data": 2, ".rodata": 3}


def pack_words(words) -> bytes:
    """Pack a sequence of 32-bit words little-endian."""
    return struct.pack("<" + "I" * len(words), *words)


def build_elf(text: bytes = b"", data: bytes = b"", rodata: bytes = b"", symbols=()) -> bytes:
    """Return a minimal ELF64 object.

    ``symbols`` is an iterable of ``(name, section, value, size)``; ``section``
    must be one of ``".text"``, ``".data"`` or ``".rodata"``.
    """
    symbols = list(symbols)
    have_syms = bool(symbols)

    names = ["", ".text", ".data", ".rodata"]
    if have_syms:
        names += [".symtab", ".strtab"]
    names += [".shstrtab"]

    shstr = bytearray()
    name_off = {}
    for name in names:
        name_off[name] = len(shstr)
        shstr += name.encode() + b"\0"

    blobs = {".text": text, ".data": data, ".rodata": rodata}

    if have_syms:
        strtab = bytearray(b"\0")
        entries = [struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0)]
        for name, section, value, size in symbols:
            off = len(strtab)
            strtab += name.encode() + b"\0"
            entries.append(
                struct.pack("<IBBHQQ", off, _ST_INFO, 0, _SECTION_INDEX[section], value, size)
            )
        blobs[".symtab"] = b"".join(entries)
        blobs[".strtab"] = bytes(strtab)
    blobs[".shstrtab"] = bytes(shstr)

    order = names[1:]
    offset = 64
    placed = {}
    for name in order:
        offset = (offset + 7) & ~7
        placed[name] = offset
        offset += len(blobs[name])
    shoff = (offset + 7) & ~7

    shdrs = [struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)]
    for name in order:
        link = names.index(".strtab") if name == ".symtab" else 0
        info = 1 if name == ".symtab" else 0
        entsize = 24 if name == ".symtab" else 0
        align = 8 if name in (".text", ".data", ".rodata", ".symtab") else 1
        shdrs.append(
            struct.pack(
                "<IIQQQQIIQQ",
                name_off[name],
                _TYPES[name],
                _FLAGS.get(name, 0),
                0,
                placed[name],
                len(blobs[name]),
                link,
                info,
                align,
                entsize,
            )
        )

    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\0" * 8
    ehdr = ident + struct.pack(
        "<HHIQQQIHHHHHH",
        1,  # e_type = ET_REL
        0xB7,  # e_machine = AArch64
        1,  # e_version
        0,  # e_entry
        0,  # e_phoff
        shoff,  # e_shoff
        0,  # e_flags
        64,  # e_ehsize
        0,  # e_phentsize
        0,  # e_phnum
        64,  # e_shentsize
        len(names),  # e_shnum
        names.index(".shstrtab"),  # e_shstrndx
    )

    buf = bytearray(ehdr)
    for name in order:
        if len(buf) < placed[name]:
            buf += b"\0" * (placed[name] - len(buf))
        buf += blobs[name]
    if len(buf) < shoff:
        buf += b"\0" * (shoff - len(buf))
    buf += b"".join(shdrs)
    return bytes(buf)


def opp_bytes(entries) -> bytes:
    """Serialise ``(freq, volt, vsram, posdiv, vaging, power)`` tuples."""
    out = bytearray()
    for entry in entries:
        out += struct.pack("<IIIIII", *entry)
    return bytes(out)


# The instruction window used by patch.UNLOCK_WORKING_OPP_TABLE.
PATCH_CONTEXT = (0x1A9F07E9, 0x2A090108, 0x528004AB, 0x7100011F, 0x1A8A1164)


def text_with_context(pre: int = 4, post: int = 4, copies: int = 1) -> tuple[bytes, int]:
    """Return ``.text`` bytes with the patch context and its offset.

    ``pre`` and ``post`` padding words use the ``nop`` encoding so they cannot
    accidentally match the anchor.
    """
    words = [0xD503201F] * pre
    at = len(words) * 4
    for _ in range(copies):
        words += list(PATCH_CONTEXT)
    words += [0xD503201F] * post
    return pack_words(words), at + 4  # site is the second context word
