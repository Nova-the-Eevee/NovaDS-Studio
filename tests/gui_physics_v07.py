import tkinter as tk
from pathlib import Path
from PIL import ImageGrab
from novads.editor import Editor
from novads.model import load_project
root=tk.Tk();ed=Editor(root)
p=Path('examples/Physics_Playground_v0.7/Physics_Playground.novads.json').resolve()
ed.project=load_project(p);ed.project_path=p;ed._project_loaded()
ed.selected_id=1;ed._show_inspector()
root.update();root.update()
assert ed._find_object()['collider'] is True
assert ed._find_object()['gravity']==530
ImageGrab.grab().save('Editor_Preview_v0.7.png')
ed.inspector_canvas.yview_moveto(0.52)
root.update();root.update()
ImageGrab.grab().save('Physics_Inspector_v0.7.png')
root.destroy()
print('GUI physics smoke passed')
