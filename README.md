# dragonkick
Tired of the tedious, click-heavy setup for a new Ghidra project? `dragonkick` is a colorful command-line tool built to get you from zero to reversing in seconds. It kicks things off by hunting down every shared library dependency for your target binaries. From there, it automatically spins up a new Ghidra project, yanks in your targets and all their libs, and run the initial analysis for you. Tell it to decompile every function and it will neatly dump all the C code into a fresh Git repo, useful to inspect with other static analysis tool like `semgrep`. `dragonkick` handles all the boring prep work so you can get reversing.

---
## Install
```
pip install git+https://github.com/wreckinglabs/dragonkick
```
---
## Demo
[![asciicast](https://asciinema.org/a/qmci5rrWoI8a11UpS8qepcRvh.svg)](https://asciinema.org/a/qmci5rrWoI8a11UpS8qepcRvh)

---
## TODOs
- Allow running other Ghidra scripts with the analysis
- Support for non-ELF binaries
- Better decompiled code source management (e.g. tracking function rename/retype etc.)
