# Changelog

## v1.1.1 — Banner packaging fix

- Fixed project icon path across recursive devkitPro `make` invocations, resolving `Could not open 'icon.bmp'` during ROM creation.
- Maintains v1.1's alternating-frame Dual 3D implementation.
- The included Dual 3D demonstration was reported working in melonDS and on original DS Lite hardware.
- GitHub source package updates project version identification and documentation without altering GPU rendering logic.

## v1.1 — Project properties and Dual 3D

- Added project name, author, description, traditional NDS title/subtitle/creator, and custom icon importing.
- Added experimental Dual 3D mode using alternate captures and separate top/bottom cameras.
- Added a dedicated editable Dual 3D camera demonstration.

## v1.0 — Playable mini-game milestone

- Introduced Nova's Star Trail playable example, scene progression and replay state fixes.
- Retained the 2D engine, real Lua 5.4.9 scripting, textured OBJ models, animation, basic 3D physics and exporter.

See [historical notes](docs/HISTORY_v0.4.md) for older development background.

- Licensing: clarified MIT for original code/docs and distinct sample-media rights before GitHub publication.
