import sys, tkinter as tk
from pathlib import Path
from PIL import ImageGrab
from novads.editor import Editor
from novads.model import load_project
from novads.tilepainter import TilePainter
root=tk.Tk();ed=Editor(root)
proj=Path('examples/Tilemap_Parallax_v0.5.3/Tilemap_Parallax.novads.json').resolve()
ed.project=load_project(proj);ed.project_path=proj;ed._project_loaded()
root.update();root.update()
ImageGrab.grab().save('Editor_Preview_v0.5.3.png')
pt=TilePainter(ed,'top',0)
pt.win.update();pt.win.update()
ImageGrab.grab().save('Tilemap_Painter_v0.5.3.png')
assert len(pt.tilepics)==256
assert pt.width==64
pt.win.destroy();root.destroy()
print('GUI smoke test PASS')
