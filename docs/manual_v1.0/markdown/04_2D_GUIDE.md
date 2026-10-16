# Building 2D games

NovaDS's 2D system uses the DS's hardware sprites (OBJ/OAM) and tile/background layers rather than drawing every image into a software framebuffer.

## Sprites and importing PNGs

**Object → Import PNG Sprite…** copies a PNG to your project, converts it to DS-compatible 4bpp sprite graphics at export and creates a Sprite2D object.

Common supported frame sizes include 8×8, 16×16, 32×32, 64×64 and supported rectangular combinations; not every arbitrary dimension is supported. Source PNGs must be non-interlaced and decoded by NovaDS's built-in PNG reader. Prefer transparent **RGBA**, and stay within **15 opaque colors + transparent** for faithful color reproduction. Extra colors are quantized.

For animation, **Object → Import PNG Sprite Sheet…** accepts a sheet with dimensions divisible by 8 (up to 256×256); specify the **frame width and height**. The current exporter accepts up to **16 frames per asset**.

In the inspector, set `frame`, `fps`, `loop`, `flip_x`, `flip_y`, rotation `angle` and `scale_x/y`. In Lua these use `self.frame`, `self.fps`, `self.flipX`, `self.flipY`, `self.angle`, `self.scaleX`, `self.scaleY`.

The DS has **128 OAM entries per 2D engine**, but NovaDS v1.0 intentionally limits its runtime to **64 Sprite2D objects per screen** and a limited palette budget. Rotating/scaling sprites need OAM affine matrices (32 per screen). Different sprite instances may share the same image data to save VRAM.

## Tile backgrounds and painting levels

1. Choose **Backgrounds → Top/Bottom background…** to import a 256×256 background, or **Paint … tilemap** to use the editor's tile painter.
2. For the painter, import a **128×128 PNG tileset** made of 8×8 tiles (16×16 tile choices).
3. Choose pencil, eraser or flood fill; paint the 32×32 or 64×64 map.
4. Set the layer's `name`, initial scroll, and parallax factor.
5. In Lua, update `Background.scroll()` to move that layer dynamically.

Regular tile layers are exported as 4bpp graphics. Affine background tiles use 8bpp graphics and a different map format. The exporter converts these differently because the DS hardware expects different layouts.

Two scenery layers per 2D screen are currently supported (BG2 and BG3). When using affine rotation/scale, the scene allows only one scenery layer on that screen. BG0 is reserved for the text UI.

## Scrolling and parallax

A practical platformer can follow a character and move distant scenery at a smaller ratio. Set a camera-follow target in **Backgrounds → Camera follow settings…**, then assign different parallax factors in the layer settings. Or script individual layers explicitly:

```lua
local offset = 0
function Update(dt)
    offset = offset + 15 * dt
    Background.scroll("bottom", "ground", offset, 0)
    Background.scroll("bottom", "mountains", offset * 0.25, 0)
end
```

If you use `Camera.follow()` and also manually overwrite the same layer's scroll each frame, the two systems may fight. Choose one controller per layer.

## Solid tiles and platforming collision

The tile painter can mark selected **tile IDs** as solid. The exported runtime uses a compact bitset for collision flags. For Sprite2D characters, enable their `collider` and `physics` settings and choose gravity/velocity values.

```lua
local speed = 120
function Start()
    self.physics = true
    self.collider = true
    self.gravity = 550
end
function Update(dt)
    self.vx = 0
    if Input.isDown("LEFT")  then self.vx = -speed; self.flipX = true end
    if Input.isDown("RIGHT") then self.vx = speed; self.flipX = false end
    if Input.pressed("A") and self.grounded then self.vy = -250 end
end
function OnTileCollision(tx, ty, layer)
    -- Optional: react to a solid-tile contact.
end
```

For this 2D solver, **positive Y points down**. Accordingly, downward gravity is positive and jumping velocity is negative. Collision boxes are axis-aligned even when the sprite graphics rotate.

## 2D collision objects and triggers

Any Sprite2D can opt into a collider; `solid` blocks movement, while `trigger` reports overlaps without acting like a wall. Set collider width/height and layer/mask in the inspector. Both sprite collision participants need compatible masks and layers.

```lua
function OnCollisionEnter(other)
    if other.id == 7 then
        other.visible = false
        other.collider = false
    end
end
```

**Scene resets:** When re-entering a scene in v1.0, the engine resets transforms/colliders and makes active objects visible, so collected items can reappear on replay.

## 2D + 2D compared with 3D + 2D

- In **2D+2D**, both screens can have sprites, layers and text.
- In **3D+2D**, the upper screen is the hardware 3D output; lower screen has the 2D scene, text UI and touch widgets.
- Switching modes is a project-level decision, not a runtime `Scene.load()` function. Named scenes share the chosen video mode.

## Known 2D limitations

No live tile mutation API, polygon-shaped 2D collisions, automatic full-scene streaming from storage, general purpose GUI widgets, or editable pixel-art sheet creator is shipped in v1.0. For complex world sizes, design within the hardware tilemap dimensions or extend the engine.
