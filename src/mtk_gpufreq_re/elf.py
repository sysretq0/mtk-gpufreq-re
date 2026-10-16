# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The mtk-gpufreq-re Authors

"""A minimal, dependency-free ELF64 reader and writer.

Only the subset needed to reason about relocatable Linux kernel modules is
implemented: the section table, a per-section view, little-endian 32-bit word
access, and symbol lookup through ``.symtab``/``.strtab`` when present.

The modules of interest are ``ET_REL`` objects whose section addresses are zero,
so a value reported by ``nm`` or a disassembler is an offset relative to its
section, not an absolute virtual address.  All offsets in this package follow
that convention and are documented as such.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

__all__ = ["ElfError", "Section", "Symbol", "Elf64"]

_ELF_MAGIC = b"\x7fELF"
_SHT_SYMTAB = 2
_SYMENT_SIZE = 24
_SYMENT_FMT = "<IBBHQQ"


class ElfError(ValueError):
    """Raised when a byte stream is not a usable little-endian ELF64 object."""


@dataclass(frozen=True)
class Section:
    """A single entry of the section table."""

    name: str
    index: int
    type: int
    flags: int
    addr: int
    offset: int
    size: int
    link: int
    entsize: int


@dataclass(frozen=True)
class Symbol:
    """A symbol resolved through ``.symtab``."""

    name: str
    value: int
    size: int
    section_index: int
    section: str | None


class Elf64:
    """A mutable view over a little-endian ELF64 object."""

    def __init__(self, data: bytes) -> None:
        if len(data) < 64 or data[:4] != _ELF_MAGIC:
            raise ElfError("not an ELF object")
        if data[4] != 2:
            raise ElfError("not a 64-bit ELF object")
        if data[5] != 1:
            raise ElfError("not a little-endian ELF object")

        self._buf = bytearray(data)
        (self._shoff,) = struct.unpack_from("<Q", self._buf, 0x28)
        (self._shentsize,) = struct.unpack_from("<H", self._buf, 0x3A)
        (self._shnum,) = struct.unpack_from("<H", self._buf, 0x3C)
        (self._shstrndx,) = struct.unpack_from("<H", self._buf, 0x3E)

        if self._shentsize < 64:
            raise ElfError("unexpected section header size: %d" % self._shentsize)
        if self._shnum == 0 or self._shstrndx >= self._shnum:
            raise ElfError("missing section name table")
        if self._shoff + self._shnum * self._shentsize > len(self._buf):
            raise ElfError("section table extends past end of file")

        self._sections = self._read_sections()
        self._by_name = {s.name: s for s in self._sections}
        self._symtab: Section | None = next(
            (s for s in self._sections if s.type == _SHT_SYMTAB), None
        )

    # -- construction helpers ------------------------------------------------

    def _raw_shdr(self, index: int) -> tuple[int, int, int, int, int, int, int, int, int, int]:
        at = self._shoff + index * self._shentsize
        return struct.unpack_from("<IIQQQQIIQQ", self._buf, at)

    def _read_sections(self) -> list[Section]:
        raw = [self._raw_shdr(i) for i in range(self._shnum)]
        str_off, str_size = raw[self._shstrndx][4], raw[self._shstrndx][5]
        blob = bytes(self._buf[str_off : str_off + str_size])

        def name(at: int) -> str:
            end = blob.find(b"\0", at)
            if end < 0:
                end = len(blob)
            return blob[at:end].decode("utf-8", "replace")

        out = []
        for index, r in enumerate(raw):
            sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link, _i, _a, sh_ent = r
            out.append(
                Section(
                    name=name(sh_name),
                    index=index,
                    type=sh_type,
                    flags=sh_flags,
                    addr=sh_addr,
                    offset=sh_offset,
                    size=sh_size,
                    link=sh_link,
                    entsize=sh_ent,
                )
            )
        return out

    # -- accessors -----------------------------------------------------------

    @property
    def sections(self) -> list[Section]:
        return list(self._sections)

    def has_section(self, name: str) -> bool:
        return name in self._by_name

    def section(self, name: str) -> Section:
        try:
            return self._by_name[name]
        except KeyError:
            raise ElfError("no such section: %s" % name) from None

    def section_data(self, name: str) -> bytes:
        s = self.section(name)
        return bytes(self._buf[s.offset : s.offset + s.size])

    @staticmethod
    def _check(section: Section, rel: int, size: int) -> None:
        if rel < 0 or rel + size > section.size:
            raise ElfError("access out of range in %s" % section.name)

    def read_u32(self, section: str, rel: int) -> int:
        s = self.section(section)
        self._check(s, rel, 4)
        return struct.unpack_from("<I", self._buf, s.offset + rel)[0]

    def write_u32(self, section: str, rel: int, value: int) -> None:
        s = self.section(section)
        self._check(s, rel, 4)
        struct.pack_into("<I", self._buf, s.offset + rel, value & 0xFFFFFFFF)

    def find(self, section: str, needle: bytes) -> list[int]:
        """Return every section-relative offset where ``needle`` occurs."""
        s = self.section(section)
        region = bytes(self._buf[s.offset : s.offset + s.size])
        hits = []
        start = 0
        while True:
            pos = region.find(needle, start)
            if pos < 0:
                break
            hits.append(pos)
            start = pos + 1
        return hits

    # -- symbols -------------------------------------------------------------

    def symbols(self) -> dict[str, Symbol]:
        """Resolve ``.symtab`` into ``{name: Symbol}``; empty if absent."""
        symtab = self._symtab
        if symtab is None or symtab.link >= len(self._sections):
            return {}
        strtab = self._sections[symtab.link]
        strs = bytes(self._buf[strtab.offset : strtab.offset + strtab.size])
        entsize = symtab.entsize or _SYMENT_SIZE

        out: dict[str, Symbol] = {}
        for at in range(symtab.offset, symtab.offset + symtab.size, entsize):
            st_name, _info, _other, st_shndx, st_value, st_size = struct.unpack_from(
                _SYMENT_FMT, self._buf, at
            )
            if st_name == 0:
                continue
            end = strs.find(b"\0", st_name)
            if end < 0:
                end = len(strs)
            name = strs[st_name:end].decode("utf-8", "replace")
            section = None
            if 0 < st_shndx < len(self._sections):
                section = self._sections[st_shndx].name
            out[name] = Symbol(name, st_value, st_size, st_shndx, section)
        return out

    # -- serialisation -------------------------------------------------------

    def to_bytes(self) -> bytes:
        return bytes(self._buf)

    def sha256(self) -> str:
        return hashlib.sha256(self._buf).hexdigest()
