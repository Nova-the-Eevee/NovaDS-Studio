import tkinter as tk
from pathlib import Path
from PIL import ImageGrab
from novads.editor import Editor
from novads.model import load_project
root=tk.Tk();ed=Editor(root)
p=Path('examples/Sprite_Animation_v0.6/Sprite_Animation.novads.json').resolve()
ed.project=load_project(p);ed.project_path=p;ed._project_loaded()
ed.selected_id=2;ed._show_inspector()
root.update();root.update()
ed.inspector_canvas.yview_moveto(0.39)
root.update();root.update()
ImageGrab.grab().save('Sprite_Inspector_v0.6.png')
root.destroy()
