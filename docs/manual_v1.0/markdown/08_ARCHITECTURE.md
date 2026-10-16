# Project format, exporter and runtime architecture

This chapter is for developers extending NovaDS, preparing GitHub releases, or debugging unusual DS-specific behavior.

## How the pieces fit

```
NovaDS Studio (Tkinter/Python on PC)
  ├─ novads/editor.py         editor, inspector, build launcher
  ├─ novads/model.py          clean/validate/migrate project JSON
  ├─ novads/pngassets.py      sprite PNG conversion
  ├─ novads/bgassets.py       tilemaps, palettes, affine tile export
  ├─ novads/meshassets.py     OBJ/MTL import, mesh simplification
  ├─ novads/texassets.py      RGB5551 texture export
  ├─ novads/wavassets.py      short PCM sound conversion
  ├─ novads/compiler.py       scene.c export + portable project copy
  └─ novads/preview.py       PC approximate visual preview
                  ↓
Exported devkitPro project
  ├─ Makefile, setup_lua.py
  ├─ source/scene.c           compiled asset and object data
  ├─ source/main.c            shared game loop + hardware renderer + Lua bridge
  ├─ source/nd_physics*.c/.h  collision helpers
  ├─ source/novads_runtime.h  runtime structs
  ├─ assets/, models/, sounds/, scripts/
  └─ project.novads.json     editable copy for the PC, not DS runtime input
                  ↓
            NovaDS_Game.nds
```

## The `.novads.json` file

It is a portable editor data format containing: project name, mode, background settings, asset registries, 3D camera settings, scene names, sounds and an `objects` array. New objects have unique integer IDs and a `scene` attribute. Asset paths use forward slashes and must remain *inside the project folder*.

**Subtle but important:** The internal JSON `version` field in v1.0 projects is still `5` for historical schema compatibility. That does **not** mean the engine release is version 0.5.

Example of a simplified excerpt (illustrative — omitted required defaults):

```json
{
  "format": "novads-project",
  "version": 5,
  "name": "My Game",
  "mode": "3d2d",
  "scenes": ["Title", "Level"],
  "active_scene": "Title",
  "objects": [
    {"id": 10, "type": "Cube3D", "scene": "Level", "screen": "top",
     "name": "Crate", "x": 0, "y": 0, "z": 0}
  ]
}
```

Do **not** use that excerpt as a complete project JSON. The editor's **Save** command writes the validated, complete schema, and that is the best format to copy.

## Why export-time conversion matters

NovaDS deliberately moves expensive work to the PC: PNG decoding, color reduction, tile deduplication, correct DS screen-block order, OBJ parsing, model simplification, mesh/UV quantization and animation-key baking. The DS receives arrays already laid out for its VRAM or geometry hardware.

The exporter also copies the project and assets into the output folder, so build artifacts are portable. Textures in `.mtl` files are copied with the matching OBJ materials.

## Shared runtime instead of code generation per game

`source/main.c` contains the same hardware engine and Lua API for different games. `source/scene.c` contains generated object tables, scripts and assets. That division matters: a game author shouldn't have to rewrite OAM, VRAM, rendering or collision code to place another object.

## Scene and asset lifecycle

- The project selects **one hardware video mode** for the whole ROM.
- Named scenes activate groups of objects; they do not dynamically unload/reload entirely separate VRAM contents.
- `Scene.load(name)` **queues** the transition until after the current frame's update/collision work.
- Scene entry restores authored transforms and physics/collider settings (but forces active objects visible), and triggers `Start()`. Lua environments and top-level locals are **not recreated** during a scene switch; scripts must reset their gameplay-local variables in `Start()` if they require a fresh level.
- Objects sharing the same sprite image or mesh can share exported geometry/graphics memory.

## Lua sandbox architecture

The DS embeds Lua 5.4.9. There is one VM for the application and independent Lua environments for object instances. The runtime registers native engine tables (`Input`, `Scene`, `Background`, `Camera`, `Camera3D`, `Physics3D`, `UI`, `Audio`) and the object `self` userdata.

The Lua allocator caps memory; a debug instruction hook caps callback work. Common `table`, `string`, `math`, `utf8` and base libraries are available. Disk/module access via `io`, `os`, `package` and debugging via `debug` are not exposed.

## Adding a new Lua command (maintainer workflow)

1. Implement the native C handler in `templates/main.c`.
2. Register it in `init_lua()` with the appropriate Lua table.
3. Validate all Lua inputs: type, range, screen mode, object state.
4. Add an editor option only if users need visual authoring for the feature.
5. Update the documentation and write focused tests that inspect the exported C and simulate behavior where practical.
6. Perform a **real devkitARM build**; then test melonDS and original DS/DS Lite hardware.

For changes to the project format, add migration/default handling in `novads/model.py` and a test that round-trips an old sample. Merely changing the editor widget isn't enough: the runtime's exported structures must also understand the feature.

## Source tree notes

The runtime has dedicated `nd_physics.c` and `nd_physics3d.c` helpers. It uses simple collision primitives and has no general rigid-body solver. Treat the PC preview and exported DS renderer as two distinct implementations that should agree in appearance when possible but are not identical.
