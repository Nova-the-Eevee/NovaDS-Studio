# Beginner's guide — Your first Nintendo DS game

This chapter assumes you're comfortable moving files around but have never made a NovaDS project. No prior C knowledge is necessary; the engine handles the low-level DS setup. Knowing a little Lua helps, but you can copy the examples.

## 1. Install the essentials

**On the PC:** Windows, Python 3 with Tkinter, and NovaDS Studio 1.0. The editor is Python-based and doesn't require a heavyweight game engine. On Windows, run `Run_NovaDS.bat`; alternatively run `python run_editor.py` from the extracted folder.

**To build a real ROM:** Install a working devkitPro environment with **devkitARM**, **libnds**, Nintendo DS build tools and MSYS2. NovaDS expects the conventional location `C:\devkitPro` on Windows, or an appropriate `DEVKITPRO` environment variable.

The first build prepares the official **Lua 5.4.9** source. The editor invokes its own Python for this step, then starts devkitPro's `make`. Internet is normally needed once for Lua; alternatively place `lua-5.4.9.tar.gz` next to the exported `setup_lua.py`.

## 2. Understand the two screens

Each physical DS screen is **256 × 192 pixels**. NovaDS offers two project modes:

- **2D top + 2D bottom:** hardware sprites, backgrounds and text layers on both screens.
- **3D top + 2D bottom:** hardware 3D on top, with 2D sprites/backgrounds/text on the bottom.

Choose 2D+2D for a two-screen platformer or puzzle game. Choose 3D+2D for a 3D adventure with a status display on the touch screen.

## 3. Create and save a project

1. Start NovaDS, then select **File → New Project**.
2. Choose a rendering mode (start with **2D+2D**).
3. Save using **File → Save Project As…**. Keep your project `.novads.json`, `assets/`, `scripts/`, `models/` and `audio/` together.
4. Click an object in the **Scene Tree** to see it in the **Inspector**.
5. Edit its `x`, `y`, visibility, color, sprite asset, or other available properties.

**Tip:** The editor preview is for positioning. It does not run your script's `Start()`/`Update()` callbacks or collisions. Test behavior in melonDS/DS Lite.

## 4. Add a movable 2D character

Choose **Object → Add 2D Sprite** or **Object → Import PNG Sprite…**. If importing, start with a simple **16×16 PNG** with transparent pixels. NovaDS turns it into 4bpp DS sprite graphics, quantizing opaque colors to at most 15 colors plus transparency.

Select the sprite, choose **Scripts → Create / Edit selected object's script**, and use:

```lua
local speed = 90

function Start()
    self.visible = true
end

function Update(dt)
    if Input.isDown("LEFT")  then self.x = self.x - speed * dt end
    if Input.isDown("RIGHT") then self.x = self.x + speed * dt end
    if Input.isDown("UP")    then self.y = self.y - speed * dt end
    if Input.isDown("DOWN")  then self.y = self.y + speed * dt end
end
```

`Update(dt)` runs each frame and `dt` is a time step (currently approximately **1/60 second**). `self` is the object that owns this script. A `local` variable outside the callbacks persists for that object's script instance.

**Important:** If an object has a script attached, NovaDS does **not** also apply its old built-in `controllable` movement. The Lua script controls it instead.

## 5. Put instructions on the touch screen

Add this in the same script's `Start()`:

```lua
UI.clear("bottom")
UI.print("bottom", 2, 2, "HELLO NOVADS!")
UI.print("bottom", 2, 4, "D-PAD TO MOVE")
```

Text coordinates count **8×8 character cells**, from x=0..31 and y=0..23, not individual pixels. On a **3D+2D** project, top-screen text is not available through this API.

For touch controls, call `UI.button()` in `Update()` so the button is continuously drawn and checks taps:

```lua
if UI.button("bottom", 2, 12, "WAVE") then
    self.flipX = not self.flipX
end
```

## 6. Export and build

1. Save the project.
2. Choose **File → Build .nds ROM** to export, prepare Lua and compile automatically.
3. If prompted, choose a folder to hold the exported sources.
4. Watch the separate **Build Output** window. Use **Copy Log** if anything fails.
5. On success, look for `NovaDS_Game.nds` in the export folder.

Or choose **File → Export DS Sources…**, open the exported folder in the devkitPro MSYS2 shell, and run:

```sh
make
```

If Lua hasn't been prepared and MSYS2 doesn't have Python, open PowerShell in the exported folder and run `py -3 setup_lua.py`, then run `make` in devkitPro.

## 7. Test on hardware

Test the generated `.nds` in melonDS first. On DS Lite, copy it to a compatible flashcart's microSD and launch from its menu. DS Lite does **not** have built-in SD storage or native CFW homebrew launching, so you need an appropriate flashcart.

Check both screens, sprite visibility, touch position, frame rate and input. After each new feature, do another emulator + hardware pass.

## 8. Next things to try

- Import a sprite sheet using **Object → Import PNG Sprite Sheet…** and set its FPS.
- Import a 256×256 background or paint a tilemap with **Backgrounds → Paint … tilemap**.
- Enable a collider and gravity to make a 2D platformer character.
- Switch to 3D+2D and import a `.obj` model with optional `.mtl` + `map_Kd` PNG texture.
- Open **Nova's Star Trail** to see Lua-driven collectibles, 3D physics and scene switching in a working sample project.

**You have built a game when the exported ROM runs.** Seeing a scene in the desktop preview is an important first step, but not proof the DS graphics and game logic are correct.
