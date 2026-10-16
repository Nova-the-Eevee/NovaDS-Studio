from pathlib import Path
import tkinter as tk
from PIL import ImageGrab
from novads.editor import Editor
from novads.model import load_project
root=tk.Tk()
editor=Editor(root)
project=Path(__file__).resolve().parents[1]/'examples'/'3D_Model_Lab_v0.9'/'3D_Model_Lab.novads.json'
editor.project=load_project(project)
editor.project_path=project
editor.selected_id=1
editor._project_loaded()
editor.selected_id=1
editor._show_inspector()
root.update_idletasks()
root.update()
ImageGrab.grab().save(str(project.parents[2]/'NovaDS_Studio_v0.9_preview.png'))
print('GUI mesh smoke PASS:',root.winfo_geometry(),len(editor.project['objects']))
root.destroy()
