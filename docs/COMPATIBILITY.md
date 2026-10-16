# Hardware compatibility (reported October 16, 2026)

The project owner performed hands-on gameplay checks with **Birb**, a game built entirely in NovaDS Studio. The following was reported successful on all four combinations:

| Console | Launcher | Boot / rendering / Lua / collision / audio / speed / replay |
|---|---|---|
| DS Lite | Flashcart | Passed |
| DSi | TWiLight Menu++ | Passed |
| 3DS | TWiLight Menu++ | Passed |
| 3DS | NDS Forwarder | Passed |

Each of eight checked features passed in all four configurations (32/32 reported passes) **for Birb**. This does **not** establish universal compatibility for all games or rendering modes.

## Dual 3D demonstration

The v1.1.1 Dual 3D demonstration (two independent 3D cube cameras) was reported working both in **melonDS** and on a **real Nintendo DS Lite**. Both screens appeared to update normally. **The precise per-screen FPS has not been instrumented**; 30 new frames/screen remains a performance target for scenes that maintain the required overall cadence.

Dual 3D has not yet been separately verified for this release on DSi/3DS hardware. Other 3D games and heavier scenes can trigger different VRAM, polygon budget or timing limitations. Report specific console, loader, game project and ROM build logs for problems.

## What host tests cover

The Python regression suite checks asset import, project migration, Lua/script/export integration and generated C contracts. It is not a substitute for devkitARM compilation, emulator execution or real hardware testing. See the [playtest checklist](HARDWARE_PLAYTEST.md) for repeatable test cases.
