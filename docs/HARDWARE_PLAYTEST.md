# Hardware playtest checklist — v1.1.1

Use the existing checklist below as a starting point, then test the Dual 3D demo described in [the v1.1 supplement](DUAL_3D_AND_BANNER.md). These cases are NOT all claimed to be completed.

# NovaDS Studio v1.0 — original DS / DS Lite Playtest

**Test hardware:** __________________  **Flashcart / launcher:** __________________  **Date:** __________

Compare melonDS with your DS Lite. Use the `example_export_star_trail` ROM, or freshly export the `Novas_Star_Trail.novads.json` project. Rebuild with `make clean && make` after changes.

| Check | melonDS | DS Lite | Notes |
|---|---|---|---|
| ROM compiles with devkitARM | ☐ | ☐ | |
| Title screen renders textured / colored low-poly Nova | ☐ | ☐ | |
| Bottom menu text and tap PLAY work | ☐ | ☐ | |
| Meadow texture renders (not a flat/gray plane) | ☐ | ☐ | |
| D-pad walks; camera follows; A jumps; collisions stop crates | ☐ | ☐ | |
| Crystals bob / spin; touching one hides it and increases counter | ☐ | ☐ | |
| Crystal pickup sound plays | ☐ | ☐ | |
| Blue gate rejects entry before three crystals | ☐ | ☐ | |
| After all three crystals, blue gate shows victory scene | ☐ | ☐ | |
| Red hazard triggers loss/retry screen | ☐ | ☐ | |
| Retry restores original position AND all three crystal colliders | ☐ | ☐ | |
| B returns to title; A starts a fresh level | ☐ | ☐ | |
| Holding SELECT displays 3D submission stats (not FPS) | ☐ | ☐ | |
| DSi extra RAM / CPU not required | ☐ | ☐ | |
| No black screens / hangs across five consecutive retries | ☐ | ☐ | |

## Things to report if something fails

- A screenshot of **both screens**.
- The full editor Build Output log if compiling fails.
- Which test step failed, and whether it also fails in melonDS.
- If using real DS hardware: DS / DS Lite model, flashcart kernel, and any DLDI or boot issues.

## Expected limitations

- The editor's PC viewport previews artwork and approximate 3D geometry; it does not simulate Lua gameplay or physics.
- Collisions use axis-aligned boxes even for rotated models.
- The minimap is not implemented in v1.0; the bottom screen is a text-based HUD.
- SELECT profiler shows submitted triangles / culled objects, not real GPU utilization or FPS.
- This test project uses one shared static VRAM asset setup for all named scenes.
