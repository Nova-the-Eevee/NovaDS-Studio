# Building 3D games

NovaDS uses the Nintendo DS's actual 3D engine for the **top screen** in 3D+2D mode. The bottom screen remains available for sprites, text and touchscreen controls.

## 1. Start a 3D scene

Choose **3D top + 2D bottom** when creating a project. Add a cube using **Object → Add 3D Cube** or import an OBJ using **Object → Import OBJ 3D model…**.

3D positions are in **world units**, not pixels. A typical first scene places a mesh near the origin and a camera around `(0, 0, 5)` looking toward it. The editor's preview uses approximate software rasterization; your DS will draw using its own geometry/raster hardware.

## 2. Importing a model

NovaDS imports **Wavefront `.obj`** geometry. Export your model from Blender or Blockbench as OBJ, keeping materials in a matching `.mtl` file and placing any material textures nearby.

Supported basics:

- Vertex positions, faces and UV (`vt`) coordinates.
- Multi-material `usemtl` and MTL diffuse (`Kd`) colors.
- PNG texture references through `map_Kd`, plus an explicit per-mesh PNG override.
- Triangulation and export-time quantization to DS-friendly geometry.

For best results: triangulate where possible, use a small number of materials, apply or bake complicated modifiers before exporting, and keep the model near the origin. Not all Blender material/shader features translate to the DS.

## 3. Textures and UVs

Use a PNG texture with width and height chosen independently from **8, 16, 32, 64 or 128 pixels**. The v1.0 exporter uses a **16-bit direct-color (RGB5551)** 3D texture format: 15 color bits plus one alpha bit.

Texture memory is allocated from a **128 KB bank** for the 3D renderer. Rough costs:

| Texture | Data |
|---|---:|
| 32×32 | 2 KB |
| 64×64 | 8 KB |
| 128×128 | 32 KB |

The build rejects oversized texture sets. The editor preview is improved over early NovaDS versions but is still only an approximation of the DS texture sampler, blending and depth behavior.

## 4. Simplify Model and LOD

Choose a Mesh3D object → **Object → Simplify selected 3D model…**. Type the desired triangle target. NovaDS keeps the original OBJ and reduces mesh geometry on the **PC during export** using a quadric-error simplifier. Some LOD cases use a faster coarse-clustering approach. Textured simplification preserves UV seam constraints where possible.

**LOD (Level of Detail):** Configure a lower-detail triangle target for a mesh asset, then a `lod_distance` for the object. At longer distances, the DS switches from the full mesh to a reduced pre-exported copy.

What LOD **does not** do: dynamically re-mesh an OBJ at runtime, improve the image texture resolution, or make a model with overly complicated materials magically cheap.

## 5. Camera and renderer

Use **3D → Edit 3D camera…** to change the initial x/y/z, yaw, pitch, or field of view. Control movement in Lua:

```lua
function Update(dt)
    if Input.isDown("LEFT") then self.x = self.x - 2 * dt end
    if Input.isDown("RIGHT") then self.x = self.x + 2 * dt end
    Camera3D.setPosition(self.x, self.y + 2.5, self.z + 5.5)
    Camera3D.setRotation(0, -15)
end
```

The renderer also supports **conservative frustum/visibility culling**, distance-based LOD, hardware fog, color/brightness adjustments baked into exported materials, and a debug counter overlay enabled through **3D → 3D Rendering & Performance…**. Hold SELECT in a game with the profiler enabled to view submitted-geometry statistics. Counts are not an exact measured frames-per-second profiler.

## 6. 3D physics and gameplay

The 3D collision solver operates on simple world-space shapes: axis-aligned boxes, basic spheres as overlap proxies, and triggers. It does **not** collide with individual triangles of an arbitrary OBJ. Rotating a mesh does not rotate its AABB.

A movable player may set `self.physics = true`, `self.collider = true`, `self.gravity = -13`, and update `self.vx / vy / vz` each frame.

```lua
local speed, jump = 3, 5.5
function Start()
    self.physics = true
    self.collider = true
    self.gravity = -13
end
function Update(dt)
    self.vx = 0
    self.vz = 0
    if Input.isDown("UP") then self.vz = -speed end
    if Input.isDown("DOWN") then self.vz = speed end
    if Input.pressed("A") and self.grounded then self.vy = jump end
end
```

In 3D, **positive Y points up**. Gravity therefore usually has a negative value, and jump velocity a positive value. This differs from the 2D screen-coordinate convention!

Raycasting: `Physics3D.raycast(x,y,z, dx,dy,dz, distance, ignoreId)` finds the closest enabled 3D collider along a ray (using simple box proxies). It is suitable for interaction tests, not precision hit detection on arbitrary triangles.

## 7. Keyframe and mesh-frame animations

The **3D Animation Timeline…** offers a single named clip per 3D object. A clip can contain position keyframes, Y-axis rotation, uniform scale, or a list of separate OBJ mesh frames. The engine interpolates transform keys and selects mesh frames using baked ROM data.

```lua
function Start()
    self:playAnimation("Bounce")
end
function Update(dt)
    if Input.pressed("X") then self.animationSpeed = 2 end
    if Input.pressed("B") then self:restartAnimation() end
end
```

There is no skeletal rig importer or skinned vertex animation in v1.0. A physics-driven object cannot simultaneously use animated transform keys as authored through the editor.

## 8. Build a game, not just a mesh viewer

Explore the **Nova's Star Trail** project: its `player.lua` demonstrates movement, following camera, triggered crystal collection, UI updates, sounds, raycasting and transitions between Title, Level, Win and Lose. Use it as the template for your first custom third-person adventure.

## DS-friendly 3D art checklist

- Simplify large meshes before exporting; the DS's 3D polygon budget is modest.
- Prefer textures of 32×32 or 64×64 where they look adequate.
- Share mesh assets and textures among several placed objects.
- Put low-detail far scenery behind LOD and enable culling.
- Avoid a large collection of distinct translucent materials.
- Test on DS Lite, not only melonDS; physics and Lua also consume CPU time.
