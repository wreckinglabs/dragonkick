# dragonkick
Tired of the tedious, click-heavy setup for a new Ghidra project? `dragonkick` is a colorful command-line tool built to get you from zero to reversing in seconds. It kicks things off by hunting down every shared library dependency for your target binaries. From there, it automatically spins up a new Ghidra project, yanks in your targets and all their libs, and run the initial analysis for you. Tell it to decompile every function and it will neatly dump all the C code into a fresh Git repo, useful to inspect with other static analysis tool like `semgrep`. `dragonkick` handles all the boring prep work so you can get reversing.

<p align="center" width="100%">
    <img width="50%" src="https://i.makeagif.com/media/3-18-2021/cC4eoe.gif">
</p>

---
## Install
```
pipx install git+https://github.com/wreckinglabs/dragonkick
```

---
## Requirements
- A copy of Ghidra 12.0 or later installed

---
## Demo
[![asciicast](https://asciinema.org/a/qmci5rrWoI8a11UpS8qepcRvh.svg)](https://asciinema.org/a/qmci5rrWoI8a11UpS8qepcRvh)

## Requirements
- https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/Features/PyGhidra/src/main/py/README.md
- https://github.com/gentoo/pax-utils/blob/master/lddtree.py

---
## TODOs
- Tag & publish v0.1.0 to PyPI
- Allow running other Ghidra scripts with the analysis
- Support for non-ELF binaries
- Better decompiled code source management (e.g. tracking function rename/retype etc.)


