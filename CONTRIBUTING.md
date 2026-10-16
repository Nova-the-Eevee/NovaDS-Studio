# Contributing to NovaDS Studio

Thanks for helping make original Nintendo DS development more accessible!

## Getting started

1. Read the [README](README.md) and [build guide](docs/BUILDING.md).
2. Run `python -m pip install -r requirements.txt` in your Python environment.
3. Run `python -m unittest tests.test_v11_banner_dual3d tests.test_export tests.test_star_trail_v10 -v` before submitting changes.
4. If you change generated ARM9 C, test an exported ROM with devkitARM and preferably melonDS / real hardware.
5. Describe expected behavior, hardware model, project mode, and how to reproduce the issue.

## Design guidelines

- Prioritize original DS / DS Lite compatibility, **4 MiB RAM**, and clear editor behavior.
- Keep Lua as the gameplay scripting language; do not silently replace it with a proprietary node system.
- Preserve existing `.novads.json` projects when extending the schema.
- Distinguish **Python source/export tests**, **real toolchain builds**, and **emulator/hardware tests** in pull requests.
- For the Dual 3D renderer, check 2D+2D and 3D+2D regressions because these modes use different VRAM layouts.
- Include small, redistributable assets in example scenes; avoid copyrighted music/graphics without permission.

Use GitHub issues for bug reports and pull requests for code changes. Do not post private file paths, API keys or personal information in logs.

## Code licensing

The original source code and documentation are MIT-licensed. See [the license](LICENSE) and [third-party/asset details](docs/LICENSING.md). Do not contribute artwork, sound or other media without the rights needed to include it publicly.
