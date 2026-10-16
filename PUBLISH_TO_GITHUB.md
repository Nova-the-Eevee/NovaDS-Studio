# Publishing this staged source to GitHub

This ZIP is prepared for the existing repository:

https://github.com/Nova-the-Eevee/NovaDS-Studio

## Important before the public push

1. **License selected:** the included `LICENSE` covers original NovaDS code and documentation under MIT. Review `docs/LICENSING.md` for sample-asset rights; the media assets are not automatically MIT-licensed.
2. Check any project screenshots/assets you plan to share.
3. Verify the build process on your Windows devkitPro installation. In particular, the v1.1.1 `icon.bmp` packaging hotfix should succeed.
4. Optionally run Python checks: `py -3 -m unittest tests.test_v11_banner_dual3d tests.test_export tests.test_star_trail_v10 -v`.

## First upload (PowerShell / Git for Windows)

```powershell
# Clone the existing, nearly empty repository
 git clone https://github.com/Nova-the-Eevee/NovaDS-Studio.git
 cd NovaDS-Studio

# Extract NovaDS_Studio_GitHub_Ready_v1.1.1.zip elsewhere.
# COPY ALL ITS CONTENTS INTO THIS CLONED DIRECTORY (not into a nested folder).
# Then:
 git status
 git add .
 git commit -m "Import NovaDS Studio v1.1.1 source and documentation"
 git push origin main
```

If Git reports you are not authenticated, use Git Credential Manager / GitHub authentication. If someone else has updated main, run `git pull --rebase` and review conflicts instead of overwriting their changes.

## After uploading

- Verify `LICENSE` (MIT, 2026 Nova-the-Eevee) and `docs/LICENSING.md` are present. The MIT license does **not** grant standalone rights in example art/audio/models.
- Enable **Issues** and add a short repository description/topics (Nintendo DS, homebrew, Lua, Python, libnds).
- Run the hosted Python checks; these do *not* compile the NDS ROM by themselves.
- Create a GitHub **Release** tagged `v1.1.1`, attach the tested editor ZIP and, if desired, an exported demo ROM you have locally compiled and verified.
- Record any new hardware results in `docs/COMPATIBILITY.md`.

The GitHub connector was used to identify the correct existing repository. **Creating this ZIP does not push code to GitHub.**
