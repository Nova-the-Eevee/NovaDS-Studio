# Editor handbook

The v1.0 editor is a Python/Tkinter desktop application. It is a **scene authoring and export tool**, not a live DS emulator. A scene is a named set of objects. The preview shows positions, graphics and approximate 3D appearance, but does **not** run Lua, 2D/3D physics, or exact hardware pipeline effects.

## Main window

- **Scene Tree:** Select objects, including objects assigned to different named scenes.
- **DS Preview:** Approximate upper/lower 256×192 screen layout, useful for placement and rough visual checks.
- **Inspector:** Edit properties on the selected object. Scroll the inspector if settings are below the window edge.
- **Build Output:** Independent, resizable console for compiler messages; supports Copy Log and Save Log.

### File menu

| Command | Function |
|---|---|
| New Project | Start a 2D+2D or 3D+2D project |
| Open Project… | Open `.novads.json` |
| Save Project / Save As… | Write project JSON; external assets remain in the project folder |
| Export DS Sources… | Generate a portable source project (`Makefile`, `source/`, Lua setup) |
| Build .nds ROM | Export, prepare Lua with the editor's Python, invoke devkitPro |
| Show Build Output… | Read compiler progress and full error logs |

Keyboard shortcuts include **Ctrl+N**, **Ctrl+O**, and **Ctrl+S**.

### Object menu

- **Add 3D Cube** and **Import OBJ 3D model…** require 3D+2D mode.
- **Simplify selected 3D model…** sets an export-time polygon reduction target.
- **Add 2D Sprite**, **Import PNG Sprite…**, **Import PNG Sprite Sheet…** create sprite assets/objects.
- **Delete Selected** removes the currently selected object from the project.

An object's **ID** is the integer used by `Scene.get(id)` and collision callbacks. Prefer stable IDs when building gameplay scripts. Names are mainly editor labels; note that `self.name` currently returns the generic string `"Object"`, not the editor name.

### 3D menu

| Command | Notes |
|---|---|
| Edit 3D camera… | Position, yaw, pitch, field of view |
| 3D Rendering & Performance… | Culling, fog, baked brightness, optional profiler |
| Import OBJ… | Copies model/MTL/PNG material sources into your project |
| Simplify selected mesh… | Same simplification function as Object menu |
| 3D Animation Timeline… | One named clip/object: transform keys and/or mesh frames |

### Backgrounds menu

There are first and second scenery layer entries per 2D screen (BG2 and BG3). The editor provides **Paint TOP/BOTTOM tilemap** commands, background import/options, and **Camera follow settings…**. The text UI reserves the BG0 console layer; affine scenes have one scenery layer instead of two. Top 2D backgrounds are not available in 3D+2D mode.

### Scripts menu

- **Create / Edit selected object's script**: write real Lua 5.4 source. Scripts are separate `.lua` files inside the project.
- **Attach existing script…**: reuse a script file on another object. Lua script globals are private per object instance.
- **Remove script**: detach the script, without deleting the file on disk.

A script can define `Start`, `Update`, collision callbacks, and `OnAnimationFinished`. See the Lua API reference.

### Scenes & Sound menu

- **Create scene…** adds a named scene (up to eight in v1.0).
- **Select preview scene…** changes what is visible in the editor.
- **Import WAV sound…** copies supported WAV files into the project.
- **Hardware budget…** estimates memory used by converted assets.

## Working with scene objects

**Sprite2D** properties: screen, position (pixels), image asset, animation FPS/frame, flip X/Y, angle, scale X/Y, control speed, collider/trigger/solid flags and 2D velocity/gravity/friction.

**Cube3D** properties: position (world units), size, spin, color, 3D collider/physics, optional transform animation.

**Mesh3D** properties: imported mesh asset, transform, size, color tint/material overrides, simplification/LOD targets, 3D collider/physics, optional baked animation. OBJ geometry may be shared among objects.

## Three rules that prevent common problems

1. **Save the project before importing external assets.** NovaDS needs a project folder into which it can copy referenced models and images.
2. **Keep assets together.** Do not break the relative paths stored in JSON. A successful export copies assets into the output folder automatically.
3. **Test the ROM.** GPU palette formats, depth ordering, affine transforms and timing can differ from the desktop approximation.

## Sample project to study

The best end-to-end v1.0 example is `examples/Novas_Star_Trail_v1.0/Novas_Star_Trail.novads.json`:

- `scripts/title.lua` — touch menu and scene loading.
- `scripts/player.lua` — 3D movement, jump, camera, UI, pickups, raycast, hazards.
- `scripts/win.lua` and `scripts/lose.lua` — end screens and replay.
- `models/` — OBJ, MTL, textures.
- `audio/` — short WAV effects.

Start by changing one variable, then rebuilding. Editing ten systems simultaneously makes DS-specific bugs much harder to isolate.
