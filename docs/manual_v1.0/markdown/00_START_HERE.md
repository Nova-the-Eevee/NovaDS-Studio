# NovaDS Studio 1.0 — Documentation

**A visual Nintendo DS / DS Lite editor with native DS rendering and embedded Lua 5.4.9.**

NovaDS lets you assemble sprite or 3D scenes on a PC, attach Lua scripts, import assets, and export source code that devkitPro builds into a Nintendo DS `.nds` ROM. It targets original DS / DS Lite limits, not the DSi's extra CPU and memory.

> **Read this first:** Version 1.0 supports **2D on both screens** or **3D top + 2D bottom**. **Dual 3D is planned, not implemented.** The PC editor approximates the appearance of scenes but does **not** execute gameplay Lua or physics. Hardware testing remains essential.

## Choose your path

| I want to… | Read |
|---|---|
| Make my first working game | [01 — Beginner's guide](01_BEGINNERS_GUIDE.md) |
| Learn the menus and inspector | [02 — Editor handbook](02_EDITOR_HANDBOOK.md) |
| Write Lua scripts | [03 — Lua API reference](03_LUA_API.md) |
| Make platformers, tilemaps and sprite animations | [04 — 2D guide](04_2D_GUIDE.md) |
| Import OBJ models and build 3D games | [05 — 3D guide](05_3D_GUIDE.md) |
| Build a `.nds` and fix errors | [06 — Building and troubleshooting](06_BUILD_TROUBLESHOOTING.md) |
| Fit games into original DS hardware | [07 — Hardware and limits](07_HARDWARE_LIMITS.md) |
| Understand scene files and engine internals | [08 — Project format and architecture](08_ARCHITECTURE.md) |
| Start with short copyable Lua recipes | [09 — Lua cookbook](09_LUA_COOKBOOK.md) |
| Check unsupported features | [10 — Known limits](10_KNOWN_LIMITS.md) |

## Fastest way to try NovaDS

1. On Windows, extract `NovaDS_Studio_v1.0.zip` and run `Run_NovaDS.bat`.
2. Open `examples/Novas_Star_Trail_v1.0/Novas_Star_Trail.novads.json`.
3. Explore the scene tree, select an object and inspect its properties.
4. Choose **File → Build .nds ROM** (requires devkitPro, devkitARM, libnds and normal DS tools).
5. Test `NovaDS_Game.nds` in melonDS, then on your DS Lite with a functioning homebrew flashcart.

**Project `.novads.json` files are editor source.** The exported `.nds` does not parse JSON at runtime: the exporter converts scenes, graphics and Lua to C data compiled into the ROM.

## Reading conventions

- **Implemented:** verified in the v1.0 source tree, not necessarily tested on every DS or flashcart.
- **Example:** copy into an object-attached `.lua` script unless the text says otherwise.
- **World units** are used for 3D; **pixels** for 2D sprite positions.
- Code examples use **actual v1.0 API names**, not proposed future functions.

## Recommended first experiment

Open the Star Trail project, change the movement speed in `scripts/player.lua` from `2.8` to `4.0`, save, build, and compare in melonDS. That tests the complete editor → Lua → exporter → compiler → ROM workflow with minimal risk.
