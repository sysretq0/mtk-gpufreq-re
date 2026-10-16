<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-16

Initial release: the GPU DVFS reverse-engineering result plus a packaged toolkit.

### Added

- **ELF64 toolkit** (`mtk_gpufreq_re.elf`): a dependency-free reader/writer for
  the `ET_REL` kernel modules, with section access, 32-bit word access, byte
  search and `.symtab` resolution.
- **OPP decoder** (`mtk_gpufreq_re.opp`): decodes six-`u32`, 24-byte OPP entries
  and renders them the way the driver's proc node does.
- **Anchored patcher** (`mtk_gpufreq_re.patch`): `UNLOCK_WORKING_OPP_TABLE`
  clears the working-table selector (`orr w8, w8, w9` -> `mov w8, wzr`) so the
  working table becomes `signed[0..44]`. The patcher requires a unique suffix
  anchor, re-checks the prefix context, and exposes a `stock`/`applied`/`absent`
  state machine.
- **CLI** (`mtk_gpufreq_re.cli`): `info`, `check`, `unlock`, `opp`, `limits`, with
  a reference-build sha256 guard and an explicit `--force`.
- **Registry** (`mtk_gpufreq_re.known`): reference module identity, table
  geometry, probe globals, device-tree properties and the limiter identifiers.
- **Tests**: stdlib `unittest` suite (62 tests) with synthetic ELF fixtures; no
  vendor binary required.
- **Docs**: architecture (including the wrapper's delegation and the one cached
  count), OPP tables, patching, limiters and reverse-engineering notes.
- **RE evidence** (`reverse/`): curated `symbols.csv`, the resolved
  function-pointer tables (`fp-tables.tsv`) and the disassembly window around the
  patched site.

### Findings captured

- GPU DVFS is a platform/wrapper split; the wrapper delegates every table and
  limiter access to the platform through registered function-pointer tables, so a
  platform-only patch propagates to `/proc/gpufreqv2/*`.
- The signed OPP table `g_default_gpu` holds 45 entries; stock exposes only
  `signed[7..44]` (38) because a segment/efuse flag (optionally forced from the
  `max_gpufreq_support_off` device-tree property) selects the trimmed table.
- The SEGMENT limiter ceiling is the overclock cap; on the reference device the
  default is `ceiling 0`, `floor count - 1`.

[Unreleased]: https://github.com/sysretq0/mtk-gpufreq-re/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sysretq0/mtk-gpufreq-re/releases/tag/v0.1.0
