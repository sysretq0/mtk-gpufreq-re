<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Contributing to mtk-gpufreq-re

This project documents MediaTek's GPU DVFS kernel modules and provides tooling to
inspect and patch them. Contributions that add evidence, correct inaccuracies, or
improve the tooling are welcome.

## Ground rules

* Be respectful and constructive; the project follows the spirit of the
  [Contributor Covenant](https://www.contributor-covenant.org/).
* Do not submit vendor kernel modules, firmware blobs, or anything you are not
  permitted to redistribute. [`NOTICE`](NOTICE) states what is and is not covered.
* Keep the package dependency-free. The installable code under
  `src/mtk_gpufreq_re/` must run on the standard library alone.
* By contributing, you agree that your work is licensed under
  `GPL-3.0-or-later`.

## Development setup

Python 3.9 or later. No runtime dependencies.

```sh
git clone <this repo> mtk-gpufreq-re
cd mtk-gpufreq-re

# Run the tests with the standard library only:
make test          # = PYTHONPATH=src python3 -m unittest discover -s tests -v

# Optional: lint and format with ruff:
python -m pip install -e '.[dev]'
make lint
make fmt
```

The test suite builds its own minimal ELF64 objects and never requires a vendor
module.

## Where to contribute

Suitable starting points:

* Resolve the open questions at the end of
  [`docs/reverse-engineering.md`](docs/reverse-engineering.md): the
  `gpueb-support` IPI path and the intended use of `max_gpufreq_support_off`.
* Add support for other MediaTek GPU DVFS modules. Extend
  `src/mtk_gpufreq_re/known.py` with the new build's identity and offsets, and add
  a patch entry in `src/mtk_gpufreq_re/patch.py` with a unique anchor.
* Add OPP-table decoders for other named tables.

## Guidelines

1. **Reproducibility.** Every new claim about behaviour must be traceable to a
   symbol, a disassembled function, or a test. Cite the section-relative offset.
2. **Tests.** Code changes require tests under `tests/`. The suite must pass with
   `python -m unittest` and no extra packages.
3. **Style.** Match the surrounding code: 4-space indentation,
   `from __future__ import annotations`, and an SPDX header on new files:
   `# SPDX-License-Identifier: GPL-3.0-or-later`.
4. **State uncertainty explicitly.** Mark inferred or speculative findings as such
   in the relevant docstring, comment or document.
5. **Offsets** are section-relative values in an `ET_REL` object (`.text` and
   `.data` are separate sections), not link-time virtual addresses.

## Commits and pull requests

* Use clear, imperative commit subjects, for example
  `patch: add stack-domain unlock`.
* Reference the issue being addressed.
* Ensure `make test` and `make lint` pass; CI runs both.
* Describe the evidence in the pull request: which module, which symbol, and how
  the result was verified.

## Reporting bugs and asking questions

Open an issue with the device model, the kernel/MTK generation, the module's
sha256 and vermagic, the exact command run, and the observed versus expected
output.
