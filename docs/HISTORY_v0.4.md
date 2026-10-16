# NovaDS Studio v0.4.3 — Build window and small-screen editor fixes 🦊

## What changed in v0.4.3

- **Build Output is now a separate, resizable window** instead of a three-line box at the bottom of the editor. Open it with **Build Output** in the toolbar or **File → Show Build Output**. It supports scrollbars, **Copy Log**, **Save Log...**, and **Clear**.
- Compiler output appears **as it arrives**, including stderr. No 20,000-character cutoff; the complete text remains available for sharing.
- The editor fits the current monitor, including compact resolutions; the inspector scrolls and the DS preview scales down to fit.
- The Windows Build button prefers devkitPro's `msys2/usr/bin/bash.exe` and explicitly sets `DEVKITPRO`, `DEVKITARM`, and the compiler path when launching it, rather than assuming the Windows editor inherited the devkitPro shell settings.
- Build calls cannot overlap. Errors are displayed in the log window rather than being squeezed into an off-screen box. A failed build reports the subprocess exit code.
- The **v0.4.2 Lua header fix remains included**, along with the earlier default-Makefile-target fix.

### How to install

Extract the full v0.4.3 ZIP to a fresh directory and run `Run_NovaDS.bat`, or **replace only `novads/editor.py`** in your v0.4.2 installation using the separate Editor Hotfix ZIP. You do **not** need to regenerate your export just to make the build output readable; select your existing project and build/export normally.

### Build troubleshooting

Press **Build ROM**, select an export directory if prompted, and watch the **Build Output** window. If the build fails, click **Copy Log** and paste the error into chat. Keep the first `fatal error:` and the final `make: ***` lines if the log is long. You can also open an already exported project in devkitPro's MSYS2 terminal and run `make` directly.

**Verification:** 26 Python tests, including an automated GUI check of the log, clipboard, and simulated success/failure builds, passed. Window sizing was tested in an Xvfb 900×650 display. Actual devkitARM compilation on Windows must still be verified against your installation.

---

# NovaDS Studio v0.4.2 — Lua header/build fixes 🦊

NovaDS is a compact visual game editor for **Nintendo DS / DS Lite**. Its Python/Tkinter editor exports portable devkitPro/libnds C projects. It supports imported PNG hardware sprites, multiple scene objects, 3D cubes on the upper screen, 2D+2D mode, and **real Lua 5.4 scripting**.

**What is new:** v0.3's home-grown Lua-like bytecode compiler is gone. Scripts are now normal Lua files, parsed and executed by an embedded **upstream Lua 5.4.9 VM** on ARM9. You can use `local` variables, tables, arrays, loops, strings, functions, closures, and the built-in `math`, `string`, `table`, and `utf8` libraries.


## v0.4.2 — Lua source preparation hotfix

v0.4.1 extracted only five Lua API headers but compiled all Lua core `.c` files, which
also require internal headers such as `lprefix.h`, `lstate.h`, `lobject.h`,
`ljumptab.h`, and others. v0.4.2 prepares **all Lua 5.4.9 headers**.
If the `lua/` folder came from v0.4.1, `setup_lua.py` detects the missing
files and fetches the verified tarball again, or reads a locally supplied copy.
It now caches the verified archive in the export folder for future use.

For a current exported project, replace **only `setup_lua.py`** using the hotfix.
You may optionally replace `source/main.c` to prevent scripted sprites from
receiving duplicate D-pad movement (built-in movement now applies only to
unscripted controllable sprites). Keep your game's `source/scene.c`, PNGs,
scripts, and `Makefile`. Run `make` again. If a pre-existing failed `lapi.o`
was left behind, run `make clean` then `make`.

**Verification limits:** Lua 5.4.9 headers and file lists were checked
against its published source index; mock tarball/extraction tests pass. A
real devkitARM+Lua ROM build still needs to be performed on your machine.

## v0.4.1 hotfix — why `make` stopped after downloading Lua

The original v0.4 Makefile accidentally set `lua-prep` as the default GNU Make target.
Running `make` downloaded Lua and then did *not* invoke the ROM build.
This hotfix sets explicit default `all` targets in the root build and recursive `build/` phases.

**For an existing v0.4 export:** Replace only its `Makefile` with the one in `example_export/` from this archive, preserving your custom game `source/`, `scripts/`, and `lua/` folders. Then run `make` again.
With v0.4.2, repairing the missing headers may require one additional Lua source download. Successful completion produces `NovaDS_Game.nds`.

## Try it

1. Extract the zip and run **`Run_NovaDS.bat`** on Windows (or `python run_editor.py`). Python 3.10+ is required; the editor still has **no third-party Python dependencies**.
2. Open **`examples/HelloNova_v0.4/HelloNova.novads.json`**.
3. Select Nova, then **Scripts → Create / Edit** to view `nova_movement.lua`. You can attach any `.lua` file within the project folder.
4. **File → Export DS Sources**. Alternatively use the already generated `example_export/`.
5. In the devkitPro MSYS2 shell, run `make` inside the exported folder. On the **first build**, `make` runs `python setup_lua.py` to download and verify the **official Lua 5.4.9 source**. It compiles Lua into the ROM with the rest of the runtime. Subsequent builds reuse the prepared source. **The machine compiling must have Python 3 available.**
6. Test `NovaDS_Game.nds` in melonDS or on an original DS / DS Lite flashcart.

### No internet in your build environment?

Download **https://www.lua.org/ftp/lua-5.4.9.tar.gz** in any browser. Put that file **next to `setup_lua.py`** in the exported game folder, then run `make`. It will extract only the necessary `.c`/`.h` files into `lua/`, checking the tarball's SHA-256 first. This is a one-time step per exported build folder.

Lua 5.4.9 SHA-256:
`2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6`

No separate Lua installation, Lua scripting DLL, NitroFS, or unusual DS toolchain is required. This is the **actual Lua interpreter compiled into ARM9 homebrew**, not a substitute scripting language. We do **not** bundle the upstream source in this zip because it couldn't be downloaded in this build environment. **The `.nds` build cannot complete until `setup_lua.py` successfully prepares Lua.**

## API

You have the following accessible inside an object's `.lua` script:

```lua
local speed = 95
local items = { "berry", "star", "coin" }
local time = 0

local function movement(dt)
    if Input.isDown("LEFT")  then self:move(-speed*dt, 0) end
    if Input.isDown("RIGHT") then self:move( speed*dt, 0) end
end

function Start()
    self.health = 3              -- custom per-object fields are allowed
    self.inventory = items        -- table assigned to custom property
end

function Update(dt)
    time = time + dt             -- local persists between frames
    movement(dt)
    if Input.pressed("B") then
        self.visible = not self.visible
    end
    if Input.isDown("A") then
        self.y = 88 + 15 * math.sin(time*3)
    end
    local other = Scene.get(3)
    if other then other.visible = true end
end
```

- **Callbacks:** `Start()` called once after scene load, `Update(dt)` once per frame. `dt` is currently a **fixed 1/60 second**; if a frame is missed, movement may slow down. We will add variable time measurement later.
- **Built-in `self` fields:** `id` (read-only), `x`, `y`, `z`, `angle` (degrees), `visible` (boolean), `speed` (pixels per frame). `name` is a placeholder (`"Object"`) until runtime name strings are added. Any other string-keyed `self` field persists in that object's own userdata table. `self:move(dx,dy)` adjusts position in pixels.
- **Input:** `Input.isDown("BUTTON")`, `Input.pressed("BUTTON")`. Old spelling `Input.IsDown`/`Input.Pressed` also works. Valid buttons: `A`, `B`, `X`, `Y`, `L`, `R`, `UP`, `DOWN`, `LEFT`, `RIGHT`, `START`, `SELECT`, `TOUCH`.
- **Scene:** `Scene.get(id)` returns another object's userdata or `nil` when the ID is absent. This works for sprites and cubes, on both screens.
- **Object scripts:** The VM is shared, but each object loads a copy of its script into a **separate `_ENV`**. Top-level locals and `Start` / `Update` closures therefore maintain independent state even when multiple objects share a `.lua` file. Userdata with persistent custom fields is shared by references returned from `Scene.get()`.
- **Compatibility:** Sprite positions are in pixels. Cube XYZ positions are in 3D scene units. `angle` currently rotates a cube around Y and half that value around X; 2D sprites don't have affine rotation yet.

The first example has Lua-controlled D-pad movement for Nova, B to hide/show it, X to add to a custom health field and increase speed, Y to speed up the spinning cube, and A to reset the star's position. A second Nova animates with a Lua table. The star uses `math.sin`. **START exits** the example, as in v0.3.

### Why use a shared Lua VM?

A separate interpreter per sprite would waste too much of the original DS's 4 MB RAM. The runtime uses a shared Lua VM with **a 768 KiB allocation budget**, script execution quota (roughly 35,000 VM instructions per callback), and gradual garbage collection. If a script exceeds the budget or errors, a short error message is printed on the bottom screen; the game loop continues. The limit is a starting value to be tuned on real hardware.

**Standard library policy:** The real language and common standard libraries are available. The `io`, `os`, `debug`, and `package` libraries are deliberately not opened to avoid unsupported filesystem/module features on DS. This means `require` is not currently available. All scripts are embedded into `scene.c` and loaded from read-only ROM data, **not** from external `.lua` files on the DS.

### Known limits

- Editor preview does not execute scripts; build and run the ROM to test behavior.
- Built-in 2D sprite flipping, animation, collision, affine transforms, backgrounds and UI layers are **next milestones**, not part of v0.4.
- Scene objects cannot be spawned/deleted via Lua yet.
- Max script file size 24 KiB; scripts load independently for each attached object.
- This is a real scripting VM but not all of Lua's standard system libraries are available, for the reasons above.
- RAM and performance on the DS Lite have not been profiled yet.

## Project layout

```
novads/                   # Tkinter editor, JSON model, PNG converter, exporter
examples/HelloNova_v0.4/  # Playable script demo, PNG files, real Lua scripts
example_export/           # Ready-to-build 3D+2D C export
example_export_2d2d/      # Ready-to-build 2D+2D C export
  source/main.c           # Shared hardware + Lua runtime
  source/scene.c          # Generated images, objects and raw Lua UTF-8 source
  source/novads_runtime.h # Data tables
  setup_lua.py            # Verified upstream Lua source downloader
  Makefile                # devkitPro cross-compiler rules
  lua/                    # Generated on first build, not included in zip
```

**Lua license:** Lua is Copyright © 1994–2026 Lua.org, PUC-Rio, under the MIT license. The official version and source download live at [lua.org](https://www.lua.org/). The resulting exported ROM statically compiles its selected Lua core and standard libraries.

## Testing status

Run `python -m unittest discover -s tests -v`. Automated tests cover both 2D+2D and 3D+2D scene exports, script embedding, path validation, project migrations, and the official Lua source checksum. All included example scripts also pass the real **Lua 5.4 syntax parser** where available, and the generated source passes a **host-only C syntax check against stand-in headers**.

**Not verified:** devkitARM/libnds compilation of Lua 5.4.9, first-time Lua source download from this environment, runtime FPS or DS Lite behavior. Please send back any `make` errors or emulator screenshots so we can adapt it to your actual toolchain/hardware.
