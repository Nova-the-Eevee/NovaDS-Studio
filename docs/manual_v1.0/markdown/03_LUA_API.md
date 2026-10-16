# Lua API reference — NovaDS v1.0

This chapter describes functions actually registered in `templates/main.c`. API names are case-sensitive except for the two input aliases listed below. Examples are for **Lua 5.4.9**, not the old v0.3 scripting subset.

## Execution model

Attach a `.lua` file to an object. Each object executes its own script copy in an independent environment that inherits the global engine API. Top-level `local` variables persist between frame callbacks for that object.

```lua
local ticks = 0
function Start()
    ticks = 0
end
function Update(dt)
    ticks = ticks + 1
end
```

- `Start()` runs on scene start/entry for active scripted objects.
- `Update(dt)` runs each active frame. The current DS game loop passes `1/60` as `dt`.
- `OnCollisionEnter(other)`, `OnCollisionStay(other)`, and `OnCollisionExit(other)` receive another object for collider contacts.
- `OnTileCollision(tileX, tileY, layerName)` is used for 2D solid-tile contacts.
- `OnAnimationFinished()` fires when a non-looping **3D** clip finishes.

Script errors are printed briefly to the DS text console rather than providing a desktop stack-trace debugger. Individual callbacks have an instruction budget; the Lua allocator has a separate memory cap.

### Built-in libraries

Available: basic Lua globals, `table`, `string`, `math`, and `utf8`. The sandbox **does not open** `io`, `os`, `debug`, `package`, or arbitrary filesystem/modules. Lua tables, functions, loops, closures and strings are supported.

## Input

| API | Result | Example |
|---|---|---|
| `Input.isDown(key)` | Boolean: key is held | `Input.isDown("LEFT")` |
| `Input.IsDown(key)` | Alias | Same behavior |
| `Input.pressed(key)` | Boolean: newly pressed this frame | `Input.pressed("A")` |
| `Input.Pressed(key)` | Alias | Same behavior |
| `Input.touch()` | Touch `x, y`, or `nil` when not touched | `local x,y = Input.touch()` |

Accepted key strings: `A`, `B`, `X`, `Y`, `L`, `R`, `UP`, `DOWN`, `LEFT`, `RIGHT`, `START`, `SELECT`, `TOUCH`. Touch coordinates refer to the bottom screen in pixels.

## Scene

| API | Result | Notes |
|---|---|---|
| `Scene.get(id)` | Object userdata or `nil` | Looks up an **active scene** object by its numeric editor ID |
| `Scene.load(name)` | No return | Queues transition to a named scene for the next frame |
| `Scene.current()` | Scene name string | Useful for status/debugging |

```lua
local star = Scene.get(20)
if star then
    star.visible = false
    star.collider = false
end
Scene.load("Win")
```

The current v1.0 build can define up to eight scenes. Entering a different scene resets object transforms and collider state, makes active objects visible, and calls `Start()`, but does not re-run the Lua file's top-level code: reset `local` counters in `Start()` for replay. Calling `Scene.load()` on the already active scene does not restart it. Scenes **share the project-level backgrounds and asset setup**; selecting a new named scene does not reallocate all graphics for an entirely different level.

## Object properties (common)

All object-attached scripts see `self` and can receive other object userdata from `Scene.get()` or collision callbacks.

| Property | Type | Read/write? |
|---|---|---|
| `self.id` | integer | **Read-only** object ID |
| `self.name` | string | **Read-only**; v1.0 currently reports `"Object"` |
| `self.x`, `self.y`, `self.z` | number | Read/write position; 2D uses pixel units, 3D world units |
| `self.angle` | number | Read/write rotation angle, degrees (used for sprite or cube spin) |
| `self.visible` | boolean | Read/write render visibility |
| `self.speed` | integer | Read/write built-in sprite-control speed, 0..32 at runtime |
| `self:move(dx, dy)` | method | Add 2D-relative position offset |
| `self:move(dx, dy, dz)` | method | Add XYZ offset for 3D objects |

You can assign extra arbitrary Lua properties (for example `self.hp = 3`) to an object's userdata; they persist within that runtime object instance. Use `local` for private script variables.

## Sprite2D-only properties

| Property | Meaning |
|---|---|
| `flipX`, `flipY` | Flip sprite horizontally/vertically |
| `scaleX`, `scaleY` | Sprite scale, 0.25..4 |
| `frame` | Current sprite-sheet frame (0-based) |
| `frameCount` | **Read-only** count of frames |
| `fps` | Animation playback rate, 0..60 |
| `playing`, `loop` | Animation state and repetition |
| `vx`, `vy` | 2D velocity |
| `gravity`, `friction` | 2D physics values |
| `grounded` | **Read-only** contact flag |
| `physics`, `collider`, `solid`, `trigger` | Physics/collision switches |
| `collisionLayer`, `collisionMask` | 8-bit collision bitfields |

Methods: `self:play()` and `self:pause()` start/stop sprite-sheet playback.

```lua
function Update(dt)
    self.vx = Input.isDown("RIGHT") and 100 or 0
    self.flipX = Input.isDown("LEFT")
    if Input.pressed("A") and self.grounded then self.vy = -245 end
end
```

**Remember:** Setting `vx/vy` only moves the object automatically when the corresponding 2D physics option is enabled.

## 3D-only properties and animation

3D Cube and Mesh objects expose:

| Property | Meaning |
|---|---|
| `vx`, `vy`, `vz` | World-space velocity |
| `gravity`, `friction` | World-space movement coefficients |
| `grounded` | **Read-only** contact flag |
| `physics`, `collider`, `solid`, `trigger` | Enable simulation/contact behavior |
| `sphere` | **Read-only** current sphere-proxy mode |
| `collisionLayer`, `collisionMask` | Contact filtering bitfields |
| `animationPlaying` | Read/write 3D clip playback state |
| `animationSpeed` | 3D animation speed, 0.1..4 |
| `animationTime` | **Read-only** clip time |
| `animationName` | **Read-only** clip name or `nil` |

3D methods: `self:playAnimation("ClipName")`, `self:restartAnimation()`, `self:pauseAnimation()`, `self:resumeAnimation()`, `self:stopAnimation()`.

```lua
function Start()
    self:playAnimation("Bounce")
end
function Update(dt)
    if Input.pressed("A") then self:pauseAnimation() end
    if Input.pressed("B") then self:restartAnimation() end
end
```

v1.0 supports one baked animation clip per 3D object. `self:playAnimation(name)` requires the **exact authored clip name**; it is not a general lookup among multiple clips.

## Camera (2D) and Camera3D

| API | Parameters | Description |
|---|---|---|
| `Camera.set(screen, x, y)` | `"top"`/`"bottom"`, pixel coordinates | Set 2D camera position; disables follow |
| `Camera.follow(screen, id)` | Screen, numeric Sprite2D ID | Follow an object on that screen |
| `Camera3D.setPosition(x,y,z)` | World coordinates | Move 3D camera; each component -24..24 |
| `Camera3D.setRotation(yaw,pitch)` | Degrees | Turn the 3D camera; pitch -85..85 |

`Camera3D` calls require **3D+2D** mode. The editor also has a camera FOV property, set at export time.

## Background

| API | Parameters | Notes |
|---|---|---|
| `Background.scroll(screen, x, y)` | Screen, scroll x/y | Scroll the first scenery layer |
| `Background.scroll(screen, layerName, x, y)` | Screen, named layer, x/y | Scroll a specific layer |
| `Background.setScroll(...)` | Same as `scroll` | Alias |
| `Background.show(screen, layerName, visible)` | Screen, layer name, boolean | Hide/show an existing layer |
| `Background.transform(screen, degrees, scale)` | Screen, rotation, scale | Affine first layer only; scale 0.25..4 |

Layer names come from the background settings in the editor. **There is no `Tilemap.setTile()` Lua function in v1.0.** Tilemaps are authored and baked at export, then hardware-scrollable at runtime.

## UI (text-backed 2D console)

| API | Parameters | Return/notes |
|---|---|---|
| `UI.print(screen, x, y, text)` | Screen, column, row, string | Draw text at 8×8 character cells |
| `UI.clear(screen)` | Screen | Clear text console |
| `UI.button(screen, x, y, label)` | Screen, col, row, string | Draw `[label]`, return true if newly tapped on **bottom** screen |
| `UI.bar(screen, x, y, width, value, max)` | Screen, col, row, chars, value, max | Draw text progress bar |

Grid coordinates: x=0..31, y=0..23. The top text console is unavailable while top-screen 3D is in use. There are no native rounded-rectangle bitmap widgets in v1.0; these are efficient **console-text widgets**.

```lua
function Update(dt)
    UI.bar("bottom", 1, 4, 16, 3, 5)
    if UI.button("bottom", 1, 7, "NEXT") then Scene.load("Level") end
end
```

`UI.button()` detects a new touch press (not merely hovering/holding) and should be invoked on frames when its button should be visible.

## Audio

`Audio.play(name, volume?, pan?, loop?)` → sound channel number. `name` must match a WAV asset imported in the editor. Defaults: volume=127, pan=64 (center), loop=false. Both volume and pan use the **0..127** range.

```lua
Audio.play("collect")
Audio.play("ouch", 100, 64, false)
```

Audio is short preloaded PCM effects, not general streaming music. Stereo input WAVs are downmixed to mono when exported.

## Physics3D

`Physics3D.raycast(x, y, z, dirX, dirY, dirZ, maxDistance, ignoreId?)` returns **object, distance** when it hits a collider; otherwise returns **nil**. The engine normalizes the direction. Distances are in world units; max distance must be positive and at most 100.

```lua
local hit, dist = Physics3D.raycast(self.x, self.y, self.z, 0, -1, 0, 8, self.id)
if hit then
    UI.print("bottom", 1, 10, "HIT #" .. hit.id)
end
```

Raycasts test axis-aligned box proxies (including sphere proxies). They do **not** intersect arbitrary individual mesh triangles.

## Things that are not APIs in v1.0

Do not copy examples using `Scene.spawn()`, `Scene.destroy()`, `Tilemap.setTile()`, `UI.image()`, `Audio.stream()`, `Physics3D.addRigidBody()`, `Lighting.setDirection()`, or `Animation.blend()`; these functions are **not registered** in the v1.0 runtime.
