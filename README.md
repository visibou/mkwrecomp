# MKW Recomp

> **This project is an independent open-source research tool. It is not affiliated with, endorsed, sponsored, or supported by Nintendo. All trademarks belong to their respective owners. This project contains no copyrighted code, assets, or cryptographic keys.**

MKW Recomp builds MKW (version 1.0.0) to run natively on Windows. It isn't an emulator: the game's code is translated to C and compiled, and its graphics are replayed on Vulkan. Everything is built locally, on your PC. It uses [Switch2Recomp](https://github.com/visibou/Switch2Recomp), which is based on SwitchRecomp by MZ Labs.

**Requires a decrypted executable file provided by the user** (a folder with `exefs\` and `romfs\` inside). Nothing from the game is included or distributed. What the builder makes from your files is derived from the game: keep it on your PC and never share it.

## What you need

- The decrypted files of MKW **version 1.0.0** (the base game, no update): a folder with `exefs\` and `romfs\` inside. The builder checks the version and tells you if yours is different.
- Windows 10 or 11, 64-bit, and a Vulkan 1.3 graphics card. The low end we test on is a laptop RTX 3050 with 4 GB.
- [Git](https://git-scm.com), [Python 3.10+](https://www.python.org) and the [Vulkan SDK](https://vulkan.lunarg.com).
- About 35 GB free on the drive you build to, plus 20 GB to spare. Building on the same drive as your files saves another 22 GB, because the game's data is linked rather than copied.

## Set up (once)

```
git clone --recursive https://github.com/visibou/mkwrecomp
cd mkwrecomp
Switch2Recomp\Install.bat                       (downloads Python and GCC, once)
python -m pip install zstandard
python Switch2Recomp\tools\get_external.py      (Switch2Recomp's outside dependencies, ~650 MB, once)
```

## Build

Double-click **`MKW Recomp.bat`**, choose your folder and press **Build**. The window shows each step, a progress bar and plain-English messages. Or, from a terminal:

```
python build_mkw.py "D:\path\to\your\files" --check
python build_mkw.py "D:\path\to\your\files"
```

The builder:

1. checks your files are the supported version;
2. checks the tools and the free space;
3. translates and compiles the game's code (30-40 minutes);
4. finds and translates the shaders (about 10 minutes);
5. converts every texture once for your graphics card (about 5 minutes, ~21 GB), so places you visit for the first time don't stutter;
6. writes the settings file with good defaults, keeping any you already changed.

If it stops, run it again: it carries on where it stopped. The game ends up in `game\MKW.exe`.

## Play

Run `game\MKW.exe`, or press **Play** in the builder window. Settings are in `game\MKW.ini`, and most of them apply while the game runs. Press F1 in game for the keys.

The first time a new combination of shaders appears, it's prepared once, which can cause a short hitch. Later runs reuse it.

## What's in this repository

| File | What it is |
|---|---|
| `build_mkw.py`, `builder_gui.py`, `MKW Recomp.bat` | The builder: its steps run Switch2Recomp's general tools |
| `MKW.hints` | Code addresses (numbers, no code) that the translation needs to find every function |
| `MKW.patches.py` | The frame-rate option (`frame_pacing` in `MKW.ini`), applied while the game's code is translated on your PC |
| `MKW.default.ini` | Default settings |
| `Switch2Recomp/` | Switch2Recomp, as a git submodule |

## Not yet

- Updates (1.1 and later) and DLC.
- Online play.
- A single-file download that needs no Git, Python or Vulkan SDK.

## License and credits

MKW Recomp is free software under the **GNU Affero General Public License v3** ([LICENSE.txt](LICENSE.txt)), with the additional terms in [NOTICE.txt](NOTICE.txt). Every copy keeps the SwitchRECOMP startup screen, the NOTICE file and the credit "SwitchRecomp by MZ Labs", and anyone who conveys it publishes their source.

- **Switch2Recomp** ([github.com/visibou/Switch2Recomp](https://github.com/visibou/Switch2Recomp)): the recompiler, runtime, shader and texture tools this builder runs. Its README lists its own credits and licenses.
- **SwitchRecomp by MZ Labs**: the recompiler and runtime Switch2Recomp is built on.
- **nxnative** by seedds and **pokopia-native** by xFractals (MIT): NVN and shader work Switch2Recomp builds on, including the game's shader profile.
- The frame-rate option is adapted from the Eglantine-MKW-DynamicFPS mod (GPL-3.0).
