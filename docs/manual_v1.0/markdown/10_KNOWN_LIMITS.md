# Known limitations and roadmap

NovaDS Studio 1.0 is a **playable 2D/3D game-development milestone**, not a fully finished professional engine. These are the distinctions that matter most when designing a project.

## Current limitations

- **No Dual 3D yet.** Current modes are 2D+2D or 3D top + 2D bottom. VRAM capture/alternating-screen 3D is a future milestone.
- **Scene assets and backgrounds are shared.** Named scenes switch active objects and Lua gameplay, not independent complete VRAM scenes. A new scene cannot choose a different hardware screen mode.
- **UI is console-text based.** Text labels, bracketed touch buttons and text progress bars work. There is no full visual UI layout system with arbitrary image/button widgets.
- **No runtime spawn/delete API.** Objects are authored in the scene; hide/disable existing objects for pickups rather than calling nonexistent `Scene.destroy()`.
- **No runtime tile edit API.** Paint tilemaps in the PC editor, then export. `Tilemap.setTile` is not implemented.
- **3D collision uses proxy shapes.** No polygon-by-polygon mesh collider; rotated visible geometry keeps axis-aligned box collision.
- **No skeletal skinning.** One baked 3D animation clip per object; transform keys and mesh-frame selection are supported.
- **No dynamic directional-lighting API.** Fog and export-time color brightness are implemented, but scene light objects/programmable dynamic lights are not.
- **3D texture support is currently direct RGB5551.** Paletted 4bpp/8bpp 3D texture modes are not in the exported runtime.
- **Audio focuses on short preloaded WAV effects.** No music streaming or audio mixing UI.
- **Editor preview is approximate.** It does not execute Lua or physics, and won't reproduce all DS-specific rasterization perfectly.
- **Lua sandbox is intentionally limited.** No filesystem (`io`), OS (`os`), package loader, `debug`, or arbitrary C module imports.
- **No built-in ROM hosting/publication.** Compile on your PC and distribute your ROM/source yourself, respecting any asset licenses.

- **Scene re-entry visibility quirk:** The current runtime makes active scene objects visible when you re-enter a scene, even if an editor setup expected an initially hidden object. Script intentional hidden states in `Start()` when needed. A call to `Scene.load()` on the current scene is ignored; switch away first to restart.

## Suggested roadmap after v1.0

1. **Reliability pass:** test the full Star Trail game on DS Lite, collect build logs and verify frame pacing.
2. **3D quality:** paletted textures, optional dynamic lighting, improved material controls and more accurate editor↔DS parity.
3. **Workflow:** scene-specific asset streaming, richer UI, live debugging and runtime object lifecycle.
4. **Animation/physics:** skeletal rigs if affordable, collision mesh simplification/mesh proxies, richer camera systems.
5. **Dual 3D:** frame alternating/capture-backed second 3D view and its VRAM/performance profiler.
6. **Public release polish:** accessibility, sample projects, tutorial videos, clear license and GitHub issue templates.

## Version hygiene

When fixing an engine bug, make a **new export from the same editor version** rather than mixing `main.c`, `scene.c`, Lua source and an older Makefile arbitrarily. Keep one fully functional project and source snapshot for every major milestone.

## Feedback checklist for contributors

A good issue includes the NovaDS version, devkitPro version/toolchain, full compiler or DS error, a minimal reproducing scene and the difference between emulator and real DS Lite behavior. Specific screenshots of both DS screens help enormously.
