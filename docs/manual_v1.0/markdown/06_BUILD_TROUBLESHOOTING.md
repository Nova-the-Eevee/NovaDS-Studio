# Building, exporting and troubleshooting

## The build pipeline

```
NovaDS editor (.novads.json + assets + scripts)
    ↓ exporter on PC
source/scene.c (scene, mesh, texture, script and sound data)
source/main.c + source/*.h + Makefile + setup_lua.py
    ↓ Windows Python prepares Lua 5.4.9 source
    ↓ devkitPro / devkitARM / libnds compile + link
NovaDS_Game.nds
```

The `.nds` does not load the editor's JSON. Most graphics and Lua source are embedded into the ROM by the exporter.

## Build through NovaDS Studio

1. **Save** your `.novads.json` project.
2. Choose **File → Build .nds ROM**.
3. Select the exported game folder when prompted.
4. NovaDS prepares Lua using the same Python interpreter running the editor.
5. It starts devkitPro MSYS2 / `make` and streams output to the dedicated Build Output window.
6. Successful output is `NovaDS_Game.nds` in the exported folder.

The editor's Windows launcher searches for devkitPro in its configured location (normally `C:\devkitPro`). If it cannot find devkitPro MSYS2, install it or launch NovaDS from a properly configured terminal.

## Build manually

From the exported folder in a **devkitPro MSYS2** shell:

```sh
make
```

To force a full recompile:

```sh
make clean
make
```

If the shell has no Python and Lua files are missing, open PowerShell in the exported folder and run:

```powershell
py -3 setup_lua.py
```

Then return to devkitPro's shell and run `make`. For an offline first build, put `lua-5.4.9.tar.gz` next to `setup_lua.py` first; the preparer verifies the archive checksum.

## Error lookup table

| Symptom | Likely cause | What to check |
|---|---|---|
| `python: command not found` during `lua-prep` | MSYS2 does not provide Python | Use the editor's **Build ROM** button, or run `py -3 setup_lua.py` in PowerShell first; update old Makefiles |
| `lprefix.h: No such file or directory` | Old/incomplete Lua source extraction | Run current `setup_lua.py` again; make sure all Lua internal headers are present |
| `object_table_ref undeclared` | Old v0.9.2 C template | Replace with v1.0 `source/main.c`, re-export the project and `make clean` |
| `oamSetHidden() cannot set hide on a RotateScale sprite` | Old runtime's affine sprite cleanup | Use v1.0 runtime (v0.8.1 fix is included) |
| Gray model instead of texture | Old 3D texture-size enum bug or unbound PNG | Re-export with v1.0; check `map_Kd`, UVs, texture dimensions and VRAM budget |
| Scrambled affine BG tiles | Old affine 4bpp/8bpp conversion bug | Re-export both `scene.c` and runtime from v1.0, rather than copying only `main.c` |
| Top background invisible | Old BG bank address mismatch | Re-export with updated runtime and texture/map data |
| Editor 3D UV looks wrong, ROM looks correct | Old coarse preview texture sampling | Use v1.0 preview; always compare with hardware |
| No sprite displayed | Palette/OAM/VRAM format mismatch in old export | Re-export, verify sprite asset/visibility and current v1.0 runtime |
| Build window hides compiler errors | Old editor layout | Use v1.0's separate resizable Build Output → Copy Log |
| Runtime Lua error text appears | Bad function, invalid property or argument | Check `03_LUA_API.md` for exact API spelling, argument order and mode |
| `Source ... not found` / asset path error | Moved PNG/OBJ/MTL/WAV after import | Restore paths under the project folder or re-import assets |
| Too many palettes / texture VRAM budget | Project too large | Reuse sprite assets, simplify meshes, shrink textures, remove unused assets |

## Before reporting a bug

Send these details to whoever is helping debug:

1. NovaDS version and whether you're using a newly exported project or an old patched folder.
2. Full **Build Output** log (Copy Log) or a clear screenshot of both DS screens.
3. Whether it reproduces in melonDS, on real DS Lite, or both.
4. Minimal `.novads.json` plus its assets/scripts, not just an editor screenshot.
5. Exact steps to reproduce: initial scene, buttons pressed, expected result, actual result.

**Important:** A successful host syntax check is not the same as a successful ARM9 devkitPro build, and a correct editor preview isn't proof the ROM will render identically.

## Keeping old projects compatible

The v1.0 editor can load older NovaDS projects via migration functions. After upgrading, save a new copy and rebuild a **new** exported folder. Copying only a runtime file into an export that has obsolete `scene.c` or Makefile data may leave mismatched formats. Keep a backup of the original JSON and source zip.
