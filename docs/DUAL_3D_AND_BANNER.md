# NovaDS Studio v1.1 — NDS Banner + Experimental Dual 3D

This release extends NovaDS Studio v1.0 without changing the existing `.novads.json` format version (still version 5), so existing 2D+2D and 3D+2D projects remain readable.

## Project configuration and NDS icon

1. Open your project and choose **File → Project Properties…**.
2. Set the full **Project name**, **Description**, and **Project author**. These values remain in the editable `.novads.json` file.
3. Enter the three **NDS banner lines**: **Title**, **Subtitle**, **Creator**. Each line accepts up to 12 printable, make-safe ASCII characters. This keeps the icon text legible in DS launchers.
4. Choose an optional **32×32 PNG icon**. Save the project before importing the icon so it can be copied into your project folder. The editor converts the icon to a 16-color indexed BMP for `ndstool`; the original PNG stays with the project and is copied into exported sources.
5. **Export Sources** or **Build ROM**. The generated Makefile sets `GAME_TITLE`, `GAME_SUBTITLE1`, `GAME_SUBTITLE2`, and `GAME_ICON`, as supported by devkitPro `ds_rules`.

The three banner lines are not the same as a DS game code or a DSi/3DS HOME Menu description. They are the traditional NDS banner strings; which lines appear depends on your launcher.

If no icon PNG is selected, devkitPro's default icon is used. This does not change gameplay objects or textures.

## Dual 3D: what the hardware actually does

The NDS has **one** 3D GPU. It cannot render two separate 3D scenes simultaneously. NovaDS's experimental `dual3d` mode alternates rendering at the DS refresh rate:

- **Even frame:** render top 3D camera; capture into VRAM D.
- **Odd frame:** render bottom 3D camera; capture into VRAM C.
- The main/sub 2D video engines and physical LCD routing alternate each frame, displaying the two retained 16-bit images.
- **Target:** 30 unique frames per second on each screen, *only if the shared engine maintains 60 combined frames per second*. A slow scene reduces both rates.

It uses a traditional **FB capture** approach. Each 256×192 image consumes 96 KiB of a 128-KiB VRAM bank (C or D). VRAM A is still available for direct-color 3D textures. The captured frame on one screen can have extra latency versus conventional 3D. This technique was informed by Nitro Engine's dual-screen documentation, but is implemented separately in the NovaDS C runtime.

**Dual 3D limitations (tested with the included demo on DS Lite):**

- No hardware 2D sprites, tilemap backgrounds, or 2D text UI in `dual3d` mode. Use `3d2d` or `2d2d` when those are needed.
- The standard 3D rendering, objects, Lua, animations, and physics remain available. 3D objects must be explicitly assigned to **top** or **bottom**.
- No on-screen profiler text in Dual 3D because the 2D text layer is reserved.
- Separate top and bottom camera positions, angles, and FOV are configured through **3D → Edit 3D camera…** and **3D → Edit BOTTOM 3D camera…**.
- `Camera3D.setPosition(x,y,z)` and `Camera3D.setRotation(yaw,pitch)` affect the top camera; `Camera3D.setBottomPosition(x,y,z)` and `Camera3D.setBottomRotation(yaw,pitch)` control the bottom camera.
- The included dual-camera demonstration was compiled externally and reported working in melonDS and on an original DS Lite (October 16, 2026). This is evidence for the demonstration, not a full compatibility or performance guarantee for every 3D scene. Actual per-screen frame rate has not been instrumented.

## Test Dual 3D first

1. Open `examples/Dual3D_v1.1/Dual3D.novads.json` or compile `example_export_dual3d` with `make` in devkitPro.
2. The top screen should show a rotating **orange** cube and the bottom a rotating **blue** cube with different camera settings. No DS console text should appear.
3. In melonDS, check that both screens update independently. Moving/removing one cube in the scene should not affect the other screen's geometry.
4. Repeat with the *same `.nds` file* on your **DS Lite**, then DSi/3DS via TWiLight Menu++ if desired.
5. If the screen goes blank, shows duplicate views, flickers, or asserts, capture the exact error and build log. Keep a working 2D+2D or 3D+2D `.nds` as a compatibility baseline; the new mode does not replace those pipelines.

## Build notes

- Requires the same Windows Python + devkitPro/libnds/Lua preparation setup as v1.0.
- The editor may download the verified Lua source once; subsequent builds reuse the prepared files.
- The downloaded source archive is **not** a compiled ROM. Build the exported project with `make`.
- Automated tests cover metadata validation, icon processing, mode migration, scene export, and API wiring. Independent user testing confirmed the Dual 3D demonstration in melonDS and on DS Lite. Automated tests do not themselves build ROMs or measure real-device FPS.

### Relevant engineering references

- [Nitro Engine — dual-screen 3D methods](https://github.com/AntonioND/nitro-engine/blob/master/docs/dual-screen-3d-modes.rst)
- [devkitPro `ds_rules` — NDS banner variables](https://github.com/devkitPro/devkitarm-rules/blob/master/ds_rules)
- [devkitPro libnds video capture registers](https://github.com/devkitPro/libnds/blob/master/include/nds/arm9/video.h)
