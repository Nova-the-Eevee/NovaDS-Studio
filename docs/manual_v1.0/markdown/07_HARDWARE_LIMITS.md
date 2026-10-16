# DS hardware budgets and engine limits

NovaDS targets the **original Nintendo DS / DS Lite**: two 256×192 screens, approximately 4 MB main RAM, dedicated 2D engines and one shared hardware 3D engine. Faster DSi hardware is not assumed.

A build that compiles can still run poorly or exhaust some GPU resource. Use the editor's **Scenes & Sound → Hardware budget…** and the exported `HARDWARE_BUDGET.txt`, and then test actual frame timing on real hardware.

## NovaDS-specific guardrails (v1.0 source)

| Resource | Limit / current behavior |
|---|---|
| Display modes | 2D+2D, or 3D top + 2D bottom |
| Dual 3D | **Not implemented** |
| Screens | 256×192 each |
| Sprite instances | Runtime caps at **64 sprites per screen** (DS hardware has 128 OAM slots per engine) |
| Rotating/scaling sprites | Up to 32 affine matrices per screen |
| Unique sprite images | Validator caps at 16 unique images per screen (palette-bank constraint) |
| Sprite assets | Up to 64 named assets per project; graphics for repeated instances may be shared |
| Sprite sheet | Up to 16 frames per imported asset |
| Sprite color format | 4bpp (15 opaque colors + transparent); quantization if necessary |
| Regular tile layer | 4bpp hardware tiled background |
| Affine layer | 8bpp; only one scenery layer on that screen |
| 2D scenery layers | Up to two on each 2D screen (BG2 / BG3), in addition to text BG0 |
| Painted maps | 32×32 or 64×64 tiles (8×8 pixels per tile) |
| Named scenes | 1–8, sharing project-level background/VRAM setup |
| Mesh assets | Up to 24 named imported OBJ assets |
| Mesh simplification | Export target 0 or 4..1800 triangles per mesh asset |
| 3D textures | 16-bit direct color, dimensions 8/16/32/64/128 px per side |
| 3D texture VRAM | 128 KB dedicated bank in this implementation |
| Lua allocator | 768 KB cap (`ND_LUA_BYTES`) |
| Lua callback budget | 35,000 instruction units / guarded invocation (`ND_LUA_INSTRUCTIONS`) |
| Audio assets | Up to 16 WAVs; one sample ≤32 KB / total samples ≤128 KB |
| 3D animation | One clip per object, ≤64 transform keys and ≤16 mesh frames |

These are **version 1.0 engine limits**, not an exhaustive list of the DS hardware's absolute capabilities. For example, the DS's OAM hardware supports more slots than NovaDS currently exposes.

## Avoiding VRAM overflows

- Reuse the same sprite asset for many objects (identical sprite sheet data can be shared).
- Prefer 16×16 or 32×32 sprites where practical.
- Use tilemaps instead of full bitmaps for scenery.
- Keep the number of independent 3D textures modest and use smaller sizes.
- For 3D, a 64×64 direct-color texture is 8 KB; 128×128 is 32 KB.
- Use `Simplify Model…` and distance-based LOD on objects that do not need all their polygons up close.

## Performance: where time goes

### ARM9 CPU

Lua code, gameplay, collisions, animation updates and a portion of scene submission run on the ARM9. Avoid allocating huge tables, building long strings, or scanning every object repeatedly in `Update()`.

### 3D GPU

The original DS has a modest per-frame geometry budget (commonly described as roughly 2,048 polygons); that is a **hardware-scale planning number**, not a guarantee for every combination of materials, clipping and CPU workload. Geometry submitted behind the camera can still cost CPU time unless culled.

### Textures and tilemaps

Graphics must be in the bank and format required by the selected background/OBJ/texture mode. The history of NovaDS's background and texture bugs is a good reminder that VRAM mapping is as important as polygon count.

## Practical targets

For a first game, aim for significantly less than the maximum budget, especially if it uses Lua and collisions:

- **2D platformer:** a few character sprite sheets, reused tile graphics, modest number of interactive colliders.
- **3D adventure:** a few hundred visible polygons until profiling establishes headroom; share textures and assets.
- **Large levels:** prefer authoring/compile-time optimization over runtime geometry processing.

These are recommendations, not engine-enforced quotas. A scene with 1,000 very simple polys may be cheaper than one with fewer, costly materials or extensive collision scripting.

## Hardware testing checklist

1. Compare melonDS and a real DS Lite with identical builds.
2. Measure responsiveness while moving/jumping, not just on the title screen.
3. Test turning the camera toward and away from complex objects.
4. Check sprite layering, rotations, affine BGs and touch position.
5. Play all WAV effects; check that audio doesn't stutter.
6. Re-enter scenes to confirm collectibles and colliders reset.
7. Test the worst-case busy scene, not only the average view.
8. Record results before adding a large new feature.
