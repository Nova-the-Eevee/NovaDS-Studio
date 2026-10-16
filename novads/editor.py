"""NovaDS Studio's dependency-free Tkinter editor."""
import json
from copy import deepcopy
import os
import shlex
import shutil
import subprocess
import sys
import threading
import queue
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
from tkinter.scrolledtext import ScrolledText

from .model import new_project, clean_project, save_project, load_project, next_object_id, FORMATS, migrate_v1, migrate_v2, migrate_v3, migrate_v4
from .compiler import export_to, slug, asset_path, script_path
from .scripting import validate_script, ScriptError
from . import preview

DARK = "#172231"
PANEL = "#202D3E"
EDGE = "#35455A"
ACCENT = "#65CED2"
TEXT = "#E7F0F9"
SOFT = "#A3B6C9"


class Editor:
    def __init__(self, root):
        self.root = root
        self.root.title("NovaDS Studio 1.1 - Dual 3D + Project Properties")
        # Fit the *available* screen rather than force a window taller than it.
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        width = min(1180, max(640, screen_w - 70))
        height = min(840, max(440, screen_h - 125))
        root.geometry(f"{width}x{height}+{max(0,(screen_w-width)//2)}+{max(0,(screen_h-height)//2)}")
        root.minsize(min(820, screen_w), min(500, screen_h))
        self.root.configure(bg=DARK)
        self.project = new_project()
        self.project_path = None
        self.export_path = None
        self.selected_id = 1
        self.last_drag = None
        self.dirty = False
        self.animating = True
        self.start_time = time.perf_counter()
        self.scale = 1.65
        self.tree_syncing = False
        self.build_running = False
        self.build_events = queue.Queue()
        self.build_log_window = None
        self.build_log_text = None
        self.build_log_content = []
        self._configure_styles()
        self._make_menu()
        self._build_layout()
        self._project_loaded()
        self.root.after(40, self._animate)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.bind_all("<Control-s>", lambda _: self.save())
        self.root.bind_all("<Control-o>", lambda _: self.open())
        self.root.bind_all("<Control-n>", lambda _: self.new())
        self.root.bind("<Delete>", self._delete_shortcut)
        self.root.bind("<Escape>", lambda _: self.canvas.focus_set())

    def _configure_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=DARK)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=DARK, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=PANEL, foreground=SOFT, font=("Segoe UI", 9))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=PANEL, foreground=ACCENT, font=("Segoe UI", 11, "bold"))
        style.configure("TButton", background="#30455C", foreground=TEXT, padding=(8,6),
                        font=("Segoe UI", 9), borderwidth=0)
        style.map("TButton", background=[("active", "#40637A"), ("disabled", "#263241")])
        style.configure("TEntry", fieldbackground="#111C29", foreground=TEXT, padding=4, insertcolor=TEXT)
        style.configure("TCombobox", fieldbackground="#111C29", foreground=TEXT, background="#30455C")
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                        rowheight=27, bordercolor=EDGE, font=("Segoe UI", 10))
        style.map("Treeview", background=[("selected", "#355872")], foreground=[("selected", "white")])
        style.configure("Treeview.Heading", background="#33455A", foreground=TEXT)

    def _make_menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        for text, command, accel in [
            ("New Project", self.new, "Ctrl+N"), ("Open Project...", self.open, "Ctrl+O"),
            ("Save Project", self.save, "Ctrl+S"), ("Save Project As...", self.save_as, ""),
            ("Export DS Sources...", self.export, ""), ("Build .nds ROM", self.build, "")]:
            file_menu.add_command(label=text, command=command, accelerator=accel)
        file_menu.add_separator()
        file_menu.add_command(label="Project Properties...",command=self.edit_project_properties)
        file_menu.add_command(label="Show Build Output...", command=self.show_build_output)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._close)
        menu.add_cascade(label="File", menu=file_menu)
        object_menu = tk.Menu(menu, tearoff=False)
        object_menu.add_command(label="Add 3D Cube", command=self.add_cube)
        object_menu.add_command(label="Import OBJ 3D model...", command=self.import_obj)
        object_menu.add_command(label="Simplify selected 3D model...", command=self.simplify_obj)
        object_menu.add_command(label="Add 2D Sprite", command=self.add_sprite)
        object_menu.add_command(label="Import PNG Sprite...", command=self.import_png)
        object_menu.add_command(label="Import PNG Sprite Sheet...", command=lambda:self.import_png(sheet=True))
        object_menu.add_command(label="Delete Selected", command=self.delete_selected)
        menu.add_cascade(label="Object", menu=object_menu)
        camera_menu=tk.Menu(menu,tearoff=False)
        camera_menu.add_command(label='Edit 3D camera...',command=self.edit_camera_3d)
        camera_menu.add_command(label='Edit BOTTOM 3D camera...',command=lambda:self.edit_camera_3d(bottom=True))
        camera_menu.add_command(label='3D Rendering & Performance...',command=self.edit_render_3d)
        camera_menu.add_command(label='Import OBJ...',command=self.import_obj)
        camera_menu.add_command(label='Simplify selected mesh...',command=self.simplify_obj)
        camera_menu.add_command(label='3D Animation Timeline...',command=self.edit_animation3d)
        menu.add_cascade(label='3D',menu=camera_menu)
        backgrounds_menu=tk.Menu(menu,tearoff=False)
        backgrounds_menu.add_command(label="Top background...",command=lambda:self.edit_background('top'))
        backgrounds_menu.add_command(label="Bottom background...",command=lambda:self.edit_background('bottom'))
        backgrounds_menu.add_separator()
        backgrounds_menu.add_command(label='Paint TOP tilemap (BG2)...',command=lambda:self.paint_tilemap('top',0))
        backgrounds_menu.add_command(label='Paint BOTTOM tilemap (BG2)...',command=lambda:self.paint_tilemap('bottom',0))
        backgrounds_menu.add_separator()
        backgrounds_menu.add_command(label='TOP second layer (BG3)...',command=lambda:self.edit_background('top',1))
        backgrounds_menu.add_command(label='BOTTOM second layer (BG3)...',command=lambda:self.edit_background('bottom',1))
        backgrounds_menu.add_command(label='Paint TOP second layer...',command=lambda:self.paint_tilemap('top',1))
        backgrounds_menu.add_command(label='Paint BOTTOM second layer...',command=lambda:self.paint_tilemap('bottom',1))
        backgrounds_menu.add_separator()
        backgrounds_menu.add_command(label='Camera follow settings...',command=self.edit_camera_follow)
        menu.add_cascade(label="Backgrounds",menu=backgrounds_menu)
        script_menu = tk.Menu(menu, tearoff=False)
        script_menu.add_command(label="Create / Edit selected object's script",command=self.edit_script)
        script_menu.add_command(label="Attach existing script...",command=self.attach_script)
        script_menu.add_command(label="Remove script",command=self.remove_script)
        menu.add_cascade(label="Scripts",menu=script_menu)
        scene_menu=tk.Menu(menu,tearoff=False)
        scene_menu.add_command(label="Create scene...",command=self.create_scene)
        scene_menu.add_command(label="Select preview scene...",command=self.select_scene)
        scene_menu.add_command(label="Import WAV sound...",command=self.import_wav)
        scene_menu.add_command(label="Hardware budget...",command=self.show_budget)
        menu.add_cascade(label="Scenes & Sound",menu=scene_menu)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo(
            "NovaDS Studio", "NovaDS Studio 1.1\nOriginal Nintendo DS / DS Lite\n\n"
            "Preview is approximate. Exports real devkitPro/libnds source code.\n"
            "OBJ Mesh3D and 2D+2D supported in this prototype.\n"
            "Full Lua 5.4 scripting; source code embedded in the ROM."))
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu)

    def _build_layout(self):
        header = ttk.Frame(self.root, padding=(12,10))
        header.pack(fill="x")
        ttk.Label(header, text="✦ NOVADS STUDIO", font=("Segoe UI", 15, "bold"),
                  foreground=ACCENT).pack(side="left", padx=(4,20))
        ttk.Button(header, text="Save", command=self.save).pack(side="left", padx=3)
        ttk.Button(header, text="Export Sources", command=self.export).pack(side="left", padx=3)
        self.build_button = ttk.Button(header, text="▶ Build ROM", command=self.build)
        self.build_button.pack(side="left", padx=3)
        ttk.Button(header, text="Build Output", command=self.show_build_output).pack(side="left", padx=3)
        ttk.Label(header, text="NDS / DS Lite  •  v1.0", foreground=SOFT).pack(side="right", padx=6)

        content = ttk.Frame(self.root, padding=(10,0,10,4))
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, minsize=180, weight=1)
        content.columnconfigure(1, minsize=310, weight=3)
        content.columnconfigure(2, minsize=215, weight=1)
        content.rowconfigure(0, weight=1)

        left = ttk.Frame(content, style="Panel.TFrame", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0,8))
        ttk.Label(left, text="SCENE TREE", style="Header.TLabel").pack(anchor="w", pady=(0,10))
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._tree_selected)
        row = ttk.Frame(left, style="Panel.TFrame")
        row.pack(fill="x", pady=8)
        ttk.Button(row, text="+ Cube", command=self.add_cube).pack(side="left", padx=(0,5))
        ttk.Button(row, text="+ OBJ", command=self.import_obj).pack(side="left", padx=(0,5))
        ttk.Button(row, text="+ Sprite", command=self.add_sprite).pack(side="left", padx=(0,5))
        ttk.Button(row, text="Import PNG", command=self.import_png).pack(side="left")
        ttk.Button(row, text="Remove", command=self.delete_selected).pack(side="right")
        ttk.Label(left, text="Select an object to edit properties.\n"
                  "Click/drag objects in the preview.", style="Muted.TLabel").pack(anchor="w", pady=(8,0))

        center = ttk.Frame(content, style="Panel.TFrame", padding=8)
        center.grid(row=0, column=1, sticky="nsew", padx=(0,8))
        ttk.Label(center, text="DS SCREEN PREVIEW", style="Header.TLabel").pack(anchor="w", pady=(0,5))
        self.canvas = tk.Canvas(center, bg="#131D2B", highlightthickness=0,
                                width=360, height=470, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._canvas_click)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda _: setattr(self, "last_drag", None))
        self.canvas.bind("<KeyPress>", self._canvas_key)
        self.canvas.bind("<Configure>", self._resize_preview)
        row = ttk.Frame(center, style="Panel.TFrame")
        row.pack(fill="x")
        self.pause_btn = ttk.Button(row, text="⏸ Pause", command=self.toggle_pause)
        self.pause_btn.pack(side="left")
        ttk.Label(row, text="Preview ≠ emulator • rotate models in ROM",
                  style="Muted.TLabel").pack(side="right")

        right = ttk.Frame(content, style="Panel.TFrame", padding=12)
        right.grid(row=0, column=2, sticky="nsew")
        ttk.Label(right, text="PROJECT", style="Header.TLabel").pack(anchor="w", pady=(0,8))
        ttk.Label(right, text="Name", style="Panel.TLabel").pack(anchor="w")
        self.project_name = ttk.Entry(right)
        self.project_name.pack(fill="x", pady=(3,8))
        self.project_name.bind("<FocusOut>", self._apply_project_name)
        self.project_name.bind("<Return>", self._apply_project_name)
        ttk.Label(right, text="Render mode", style="Panel.TLabel").pack(anchor="w")
        self.mode_var = tk.StringVar(value=self.project["mode"])
        self.mode_box = ttk.Combobox(right, state="readonly", textvariable=self.mode_var,
                                     values=list(FORMATS), width=18)
        self.mode_box.pack(fill="x", pady=(3,5))
        self.mode_box.bind("<<ComboboxSelected>>", self._change_mode)
        self.mode_help = ttk.Label(right, text=FORMATS[self.project["mode"]], style="Muted.TLabel")
        self.mode_help.pack(anchor="w", pady=(0,10))
        bgrow = ttk.Frame(right, style="Panel.TFrame")
        bgrow.pack(fill="x", pady=(0,12))
        ttk.Button(bgrow, text="Top color", command=lambda: self._pick_background("top")).pack(side="left", padx=(0,4))
        ttk.Button(bgrow, text="Bottom color", command=lambda: self._pick_background("bottom")).pack(side="left")
        ttk.Button(right,text="Edit backgrounds / scrolling...",
                   command=lambda:self.edit_background('bottom')).pack(fill="x",pady=(0,5))
        ttk.Separator(right).pack(fill="x", pady=6)
        ttk.Label(right, text="INSPECTOR", style="Header.TLabel").pack(anchor="w", pady=(6,8))
        # Properties scroll on compact displays; no controls are cut off.
        inspector_frame = ttk.Frame(right, style="Panel.TFrame")
        inspector_frame.pack(fill="both", expand=True)
        inspector_canvas = tk.Canvas(inspector_frame, bg=PANEL, highlightthickness=0, borderwidth=0)
        inspector_scroll = ttk.Scrollbar(inspector_frame, orient="vertical", command=inspector_canvas.yview)
        inspector_canvas.configure(yscrollcommand=inspector_scroll.set)
        inspector_scroll.pack(side="right", fill="y")
        inspector_canvas.pack(side="left", fill="both", expand=True)
        self.inspector = ttk.Frame(inspector_canvas, style="Panel.TFrame")
        inner_id = inspector_canvas.create_window((0, 0), window=self.inspector, anchor="nw")
        self.inspector.bind("<Configure>", lambda _e: inspector_canvas.configure(scrollregion=inspector_canvas.bbox("all")))
        inspector_canvas.bind("<Configure>", lambda e: inspector_canvas.itemconfigure(inner_id, width=e.width))
        def _inspector_wheel(e):
            direction = -1 if (getattr(e, 'delta', 0) > 0 or getattr(e, 'num', 0) == 4) else 1
            inspector_canvas.yview_scroll(direction * 2, "units")
            return "break"
        inspector_canvas.bind("<MouseWheel>", _inspector_wheel)
        inspector_canvas.bind("<Button-4>", _inspector_wheel)
        inspector_canvas.bind("<Button-5>", _inspector_wheel)
        self.inspector_canvas = inspector_canvas

        footer = ttk.Frame(self.root, padding=(12,2,12,8))
        footer.pack(fill="x")
        self.status = ttk.Label(footer, text="Ready", foreground=SOFT)
        self.status.pack(anchor="w")
        self.last_message = ttk.Label(footer, text="Ready — use Build Output for full compiler logs.", foreground=SOFT)
        self.last_message.pack(anchor="w")
        self._log("NovaDS v1.0 ready. Build Output opens in a separate, resizable window.")

    def _log(self, text):
        """Show a short status without consuming vertical editing space."""
        value = str(text).rstrip()
        if value:
            self.last_message.configure(text=value.splitlines()[-1][:150])

    def _note_changed(self):
        self.dirty = True
        self._update_title()
        self._redraw()

    def _update_title(self):
        self.root.title(f"NovaDS Studio 1.1.1 - {self.project['name']}" + (" *" if self.dirty else ""))
        self.status.config(text=f"{FORMATS[self.project['mode']]}  •  "
                           f"{len(self.project['objects'])} objects  •  "
                           f"{sum(12 for o in self.project['objects'] if o['type']=='Cube3D')} cube triangles + {sum(o['type']=='Mesh3D' for o in self.project['objects'])} mesh objects  •  "
                           f"{len(self.project['assets'])} image assets")

    def _project_loaded(self):
        self.dirty = False
        self.mode_var.set(self.project["mode"])
        self.mode_help.config(text=FORMATS[self.project["mode"]])
        self.project_name.delete(0, "end")
        self.project_name.insert(0, self.project["name"])
        self.selected_id = self.project["objects"][0]["id"] if self.project["objects"] else None
        self._refresh_scene_tree()
        self._show_inspector()
        self._update_title()
        self._redraw()

    def _find_object(self):
        return next((o for o in self.project["objects"] if o["id"] == self.selected_id), None)

    def _refresh_scene_tree(self):
        self.tree_syncing = True
        self.tree.delete(*self.tree.get_children())
        for screen in ("top", "bottom"):
            group = "s:" + screen
            self.tree.insert("", "end", iid=group, text=("▣ TOP SCREEN" if screen=="top" else "▣ BOTTOM SCREEN"), open=True)
            for o in self.project["objects"]:
                if o["screen"] == screen:
                    self.tree.insert(group, "end", iid=f"o:{o['id']}", text=("▧ " if o["type"] in ("Cube3D","Mesh3D") else "✦ ")+o["name"]+" ["+o.get("scene", "Main")+"]"+("  ✎" if o.get('script') else ""))
        if self.selected_id is not None and self.tree.exists(f"o:{self.selected_id}"):
            self.tree.selection_set(f"o:{self.selected_id}")
            self.tree.see(f"o:{self.selected_id}")
        self.tree_syncing = False

    def _tree_selected(self, _=None):
        if self.tree_syncing:
            return
        selection = self.tree.selection()
        if selection and selection[0].startswith("o:"):
            self.selected_id = int(selection[0][2:])
            self._show_inspector()
            self._redraw()

    def edit_animation3d(self):
        """Edit baked keyframes in a small, resolution-independent timeline window."""
        obj=self._find_object()
        if not obj or obj['type'] not in ('Cube3D','Mesh3D'):
            messagebox.showinfo('3D Animation','Select a Cube3D or Mesh3D first.')
            return
        old=deepcopy(obj.get('animation3d'))
        initial=old or dict(name='Bounce',fps=30,loop=True,autoplay=True,duration=30,
                            keys=[dict(frame=0,x=0,y=0,z=0,yaw=0,scale=1),
                                  dict(frame=15,x=0,y=1,z=0,yaw=90,scale=1.1),
                                  dict(frame=30,x=0,y=0,z=0,yaw=0,scale=1)],mesh_frames=[])
        win=tk.Toplevel(self.root)
        win.title('NovaDS — 3D Animation Timeline')
        sw,sh=win.winfo_screenwidth(),win.winfo_screenheight()
        win.geometry(f'{min(790,sw-70)}x{min(600,sh-110)}')
        win.configure(bg=DARK)
        body=ttk.Frame(win,padding=10);body.pack(fill='both',expand=True)
        settings=ttk.Frame(body);settings.pack(fill='x')
        name=tk.StringVar(value=initial['name']);fps=tk.StringVar(value=str(initial['fps']));duration=tk.StringVar(value=str(initial['duration']))
        loop=tk.BooleanVar(value=initial['loop']);autoplay=tk.BooleanVar(value=initial['autoplay'])
        for label,var in [('Clip name',name),('FPS',fps),('Duration (frames)',duration)]:
            sub=ttk.Frame(settings);sub.pack(side='left',fill='x',expand=True,padx=3)
            ttk.Label(sub,text=label).pack(anchor='w')
            ttk.Entry(sub,textvariable=var,width=12).pack(fill='x')
        checks=ttk.Frame(body);checks.pack(fill='x',pady=4)
        ttk.Checkbutton(checks,text='Loop',variable=loop).pack(side='left',padx=4)
        ttk.Checkbutton(checks,text='Auto-play',variable=autoplay).pack(side='left',padx=4)
        columns=('frame','x','y','z','yaw','scale')
        tree=ttk.Treeview(body,columns=columns,show='headings',height=8,selectmode='browse')
        for c in columns:
            tree.heading(c,text=c.upper())
            tree.column(c,width=95 if c!='frame' else 70,anchor='center',stretch=True)
        tree.pack(fill='both',expand=True,pady=6)
        keys=[dict(k) for k in initial['keys']]
        def refresh():
            for iid in tree.get_children():tree.delete(iid)
            for k in sorted(keys,key=lambda k:k['frame']):
                tree.insert('', 'end',iid=str(k['frame']),values=[k[t] for t in columns])
        def edit_key(add=False):
            selected=tree.selection()
            if not add and not selected:return
            oldkey=next((k for k in keys if k['frame']==int(selected[0])),None) if selected else None
            key=oldkey or dict(frame=0,x=0,y=0,z=0,yaw=0,scale=1)
            dialog=tk.Toplevel(win);dialog.title('Animation keyframe');dialog.transient(win)
            frame=ttk.Frame(dialog,padding=10);frame.pack(fill='both',expand=True)
            fields={}
            for column in columns:
                row=ttk.Frame(frame);row.pack(fill='x',pady=2)
                ttk.Label(row,text=column.upper(),width=13).pack(side='left')
                var=tk.StringVar(value=str(key[column]));ttk.Entry(row,textvariable=var,width=15).pack(side='left')
                fields[column]=var
            def commit():
                try:
                    newkey={'frame':int(fields['frame'].get())}
                    for col in columns[1:]:newkey[col]=float(fields[col].get())
                    if any(k['frame']==newkey['frame'] for k in keys if k is not oldkey):
                        raise ValueError('Frame already has a keyframe')
                    if oldkey:keys.remove(oldkey)
                    keys.append(newkey);refresh();dialog.destroy()
                except ValueError as ex:messagebox.showerror('Keyframe',str(ex),parent=dialog)
            ttk.Button(frame,text='Save key',command=commit).pack(pady=6,fill='x')
        def remove_key():
            sel=tree.selection()
            if sel:
                keys[:]=[k for k in keys if k['frame']!=int(sel[0])];refresh()
        buttons=ttk.Frame(body);buttons.pack(fill='x')
        ttk.Button(buttons,text='+ Key',command=lambda:edit_key(True)).pack(side='left',padx=2)
        ttk.Button(buttons,text='Edit Key',command=edit_key).pack(side='left',padx=2)
        ttk.Button(buttons,text='Delete Key',command=remove_key).pack(side='left',padx=2)
        ttk.Label(body,text='Mesh frames: comma-separated imported mesh asset names (up to 16). Switches geometry, no skinning.').pack(anchor='w',pady=(9,2))
        meshstr=tk.StringVar(value=', '.join(initial['mesh_frames']))
        meshentry=ttk.Entry(body,textvariable=meshstr);meshentry.pack(fill='x')
        ttk.Label(body,text='Imported models: '+(', '.join(self.project['mesh_assets']) or '(none)'),wraplength=600).pack(anchor='w')
        play=ttk.Frame(body);play.pack(fill='x',pady=(8,0))
        ttk.Label(play,text='Scrub (frame)').pack(side='left')
        scrub=tk.IntVar(value=0)
        preview_label=ttk.Label(body,text='Frame 0',style='Muted.TLabel')
        def scrubbed(value):
            f=float(value)
            ks=sorted(keys,key=lambda k:k['frame'])
            if ks:
                a=ks[0];b=ks[-1]
                for j in range(1,len(ks)):
                    if f<=ks[j]['frame']:a,b=ks[j-1],ks[j];break
                t=max(0,min(1,(f-a['frame'])/max(1,b['frame']-a['frame'])))
                vals=[a[c]+(b[c]-a[c])*t for c in ('x','y','z','yaw','scale')]
                preview_label.configure(text=f'Frame {int(f)}  ·  XYZ {vals[0]:.2f}, {vals[1]:.2f}, {vals[2]:.2f}  ·  yaw {vals[3]:.1f}°  ·  scale {vals[4]:.2f}×')
        slider=tk.Scale(play,from_=0,to=max(30,initial['duration']),orient='horizontal',variable=scrub,command=scrubbed,bg=DARK,fg=TEXT,highlightthickness=0)
        slider.pack(side='left',fill='x',expand=True)
        preview_label.pack(anchor='w');scrubbed(0)
        footer=ttk.Frame(body);footer.pack(fill='x',pady=8)
        def save():
            try:
                clip=dict(name=name.get(),fps=float(fps.get()),duration=int(duration.get()),
                          loop=loop.get(),autoplay=autoplay.get(),keys=keys,
                          mesh_frames=[x.strip() for x in meshstr.get().split(',') if x.strip()])
                obj['animation3d']=clip
                clean_project(self.project)
            except (ValueError,TypeError) as ex:
                obj['animation3d']=old
                messagebox.showerror('Animation',str(ex),parent=win);return
            self._note_changed();self._show_inspector();win.destroy()
        def delete():
            obj['animation3d']=None;self._note_changed();self._show_inspector();win.destroy()
        ttk.Button(footer,text='Save animation',command=save).pack(side='left',padx=2)
        ttk.Button(footer,text='Remove animation',command=delete).pack(side='left',padx=2)
        ttk.Button(footer,text='Cancel',command=win.destroy).pack(side='right')
        refresh()

    def _show_inspector(self):
        for child in self.inspector.winfo_children():
            child.destroy()
        obj = self._find_object()
        if obj is None:
            ttk.Label(self.inspector, text="No object selected", style="Muted.TLabel").pack(anchor="w")
            return
        ttk.Label(self.inspector, text=obj["type"], style="Panel.TLabel").pack(anchor="w", pady=(0,5))
        def field(name, key):
            ttk.Label(self.inspector, text=name, style="Muted.TLabel").pack(anchor="w", pady=(4,0))
            entry = ttk.Entry(self.inspector)
            entry.insert(0, str(obj.get(key, "")))
            entry.pack(fill="x")
            def commit(event=None):
                if self._find_object() is not obj: return
                text = entry.get()
                try:
                    if key == "name":
                        value = text.strip()[:50]
                        if not value: raise ValueError("Name cannot be empty")
                    elif (key in ("x", "y", "speed", "frame", "collider_width", "collider_height", "collision_layer", "collision_mask") and obj["type"] == "Sprite2D") or (key in ("collision_layer3d", "collision_mask3d") and obj["type"] in ("Mesh3D", "Cube3D")):
                        value = int(float(text))
                    else:
                        value = float(text)
                    previous = obj.get(key)
                    obj[key] = value
                    try:
                        clean_project(self.project)
                    except ValueError:
                        obj[key] = previous
                        raise
                    if value != previous:
                        self._note_changed()
                        if key == "name": self._refresh_scene_tree()
                except (ValueError, TypeError) as exc:
                    messagebox.showerror("Invalid property", str(exc))
                    entry.delete(0, "end")
                    entry.insert(0, str(obj.get(key, "")))
            entry.bind("<FocusOut>", commit)
            entry.bind("<Return>", commit)
        ttk.Separator(self.inspector).pack(fill="x", pady=(11,5))
        ttk.Label(self.inspector, text="BEHAVIOR SCRIPT",style="Header.TLabel").pack(anchor="w")
        ttk.Label(self.inspector, text=obj.get('script') or '(no script)',style="Muted.TLabel",wraplength=230).pack(anchor="w",pady=(3,6))
        ttk.Button(self.inspector,text="Edit / Create Script",command=self.edit_script).pack(fill="x",pady=(0,4))
        srow=ttk.Frame(self.inspector,style="Panel.TFrame")
        srow.pack(fill="x")
        ttk.Button(srow,text="Attach...",command=self.attach_script).pack(side="left")
        ttk.Button(srow,text="Remove",command=self.remove_script).pack(side="left",padx=6)

        field("Name", "name")
        ttk.Label(self.inspector,text="SCENE MEMBERSHIP",style="Header.TLabel").pack(anchor="w",pady=(7,2))
        scene_choice=tk.StringVar(value=obj.get('scene',self.project['scenes'][0]))
        scene_select=ttk.Combobox(self.inspector,state="readonly",textvariable=scene_choice,
                                  values=self.project['scenes'])
        scene_select.pack(fill="x")
        def change_object_scene(_=None):
            obj['scene']=scene_choice.get()
            self._refresh_scene_tree();self._note_changed()
        scene_select.bind('<<ComboboxSelected>>',change_object_scene)
        if obj["type"] in ("Cube3D","Mesh3D"):
            if self.project['mode']=='dual3d':
                ttk.Label(self.inspector,text='3D output screen',style='Muted.TLabel').pack(anchor='w')
                v_screen=tk.StringVar(value=obj['screen'])
                screen_box=ttk.Combobox(self.inspector,textvariable=v_screen,
                                        values=['top','bottom'],state='readonly')
                screen_box.pack(fill='x')
                def set_screen(_=None):
                    old=obj['screen'];obj['screen']=v_screen.get()
                    try:clean_project(self.project)
                    except ValueError as exc:
                        obj['screen']=old;v_screen.set(old)
                        messagebox.showerror('3D output screen',str(exc));return
                    self._note_changed()
                screen_box.bind('<<ComboboxSelected>>',set_screen)
            for display, key in [("X", "x"), ("Y", "y"), ("Z", "z"),
                                 ("Size", "size"), ("Spin: deg/frame", "spin")]:
                field(display, key)
            ttk.Separator(self.inspector).pack(fill="x",pady=(8,4))
            ttk.Label(self.inspector,text="3D COLLISION & PHYSICS",style="Header.TLabel").pack(anchor="w")
            for key,label in [('collider3d','Enable 3D collider'),('solid3d','Solid static obstacle'),
                              ('trigger3d','Trigger (non-solid)'),('physics3d','Move using velocity/gravity'),
                              ('sphere3d','Sphere shape (otherwise box)')]:
                v=tk.BooleanVar(value=obj.get(key,False))
                def toggle3d(k=key,var=v):
                    before=obj.get(k,False);obj[k]=bool(var.get())
                    try: clean_project(self.project)
                    except ValueError as exc:
                        obj[k]=before;var.set(before);messagebox.showerror('Invalid 3D collider',str(exc));return
                    self._note_changed()
                ttk.Checkbutton(self.inspector,text=label,variable=v,command=toggle3d).pack(anchor="w")
            for label,key in [('Half width / radius','half_x3d'),('Half height','half_y3d'),('Half depth','half_z3d'),
                              ('Initial VX','velocity_x3d'),('Initial VY','velocity_y3d'),
                              ('Initial VZ','velocity_z3d'),('Gravity (negative = down)','gravity3d'),
                              ('Friction','friction3d'),('Layer bits','collision_layer3d'),
                              ('Mask bits','collision_mask3d')]:
                field(label,key)
            ttk.Label(self.inspector,text='3D Lua: self.vx/vy/vz, self.gravity, self.grounded. Y is up.',
                      style='Muted.TLabel',wraplength=220).pack(anchor='w',pady=4)
            ttk.Separator(self.inspector).pack(fill='x',pady=(8,4))
            ttk.Label(self.inspector,text='3D ANIMATION',style='Header.TLabel').pack(anchor='w')
            clip=obj.get('animation3d')
            ttk.Label(self.inspector,text=(clip['name']+' · '+str(len(clip['keys']))+' keys · '+str(len(clip['mesh_frames']))+' mesh frames') if clip else '(none)',style='Muted.TLabel').pack(anchor='w')
            ttk.Button(self.inspector,text='Edit 3D Animation Timeline...',command=self.edit_animation3d).pack(fill='x',pady=(2,5))
            ttk.Label(self.inspector,text='VISIBILITY & LEVEL OF DETAIL',style='Header.TLabel').pack(anchor='w',pady=5)
            option=tk.BooleanVar(value=obj.get('cull3d',True))
            def change_cull():
                obj['cull3d']=option.get();self._note_changed()
            ttk.Checkbutton(self.inspector,text='Frustum culling for this object',variable=option,command=change_cull).pack(anchor='w')
            field('LOD switch distance (world units)','lod_distance')
            if obj['type']=='Mesh3D':
                ttk.Label(self.inspector, text='3D MESH' , style='Header.TLabel').pack(anchor='w',pady=(10,2))
                ttk.Label(self.inspector,text='Model: '+str(obj.get('mesh')),style='Muted.TLabel').pack(anchor='w')
                for display,key in [('Rotation X (degrees)','rot_x'),('Rotation Y (degrees)','rot_y'),('Rotation Z (degrees)','rot_z')]:
                    field(display,key)
                texture=self.project['mesh_assets'][obj['mesh']].get('texture','')
                ttk.Label(self.inspector,text='Texture: '+(texture or 'MTL map_Kd / flat colors'),
                          style='Muted.TLabel',wraplength=210).pack(anchor='w')
                ttk.Button(self.inspector,text='Assign PNG Texture...',command=self.assign_mesh_texture).pack(fill='x',pady=3)
                ttk.Button(self.inspector,text='Use MTL Texture / No Override',command=self.clear_mesh_texture).pack(fill='x',pady=3)
                ttk.Button(self.inspector,text='Simplify Model...',command=self.simplify_obj).pack(fill='x',pady=8)
                ttk.Button(self.inspector,text='Generate automatic LOD...',command=self.set_mesh_lod).pack(fill='x',pady=3)
        else:
            for display, key in [("X (pixels)", "x"), ("Y (pixels)", "y"), ("Speed: px/frame", "speed"),
                                 ("Angle (degrees)", "angle"), ("Scale X (0.25..4)", "scale_x"),
                                 ("Scale Y (0.25..4)", "scale_y"), ("Animation FPS (0..60)", "fps"),
                                 ("Initial frame (zero-based)", "frame")]:
                field(display, key)
            for key,label in [('flip_x','Flip horizontally'),('flip_y','Flip vertically'),('loop','Loop animation')]:
                option=tk.BooleanVar(value=obj.get(key,key=='loop'))
                def toggle_flag(k=key, var=option):
                    obj[k]=var.get();self._note_changed()
                ttk.Checkbutton(self.inspector,text=label,variable=option,command=toggle_flag).pack(anchor='w',pady=2)
            ttk.Separator(self.inspector).pack(fill="x",pady=(12,5))
            ttk.Label(self.inspector,text="2D COLLISION & PHYSICS",style="Header.TLabel").pack(anchor="w")
            for key,label in [('collider','Enable box collider'),('solid','Solid obstacle'),
                              ('trigger','Trigger (passes through)'),('physics','Enable velocity / gravity')]:
                option=tk.BooleanVar(value=obj.get(key,False))
                def toggle_physics(k=key,var=option):
                    old=deepcopy(obj)
                    obj[k]=var.get()
                    if k=='solid' and var.get():obj['trigger']=False
                    if k=='trigger' and var.get():obj['solid']=False
                    try: clean_project(self.project)
                    except ValueError as exc:
                        obj.clear();obj.update(old)
                        messagebox.showerror('Collider settings',str(exc));self._show_inspector();return
                    self._note_changed()
                    if k in ('solid','trigger'):self._show_inspector()
                ttk.Checkbutton(self.inspector,text=label,variable=option,command=toggle_physics).pack(anchor='w',pady=1)
            for title,key in [
                    ('Collider width (0 = image)', 'collider_width'),
                    ('Collider height (0 = image)', 'collider_height'),
                    ('Layer bits (1..255)','collision_layer'),('Mask bits (0..255)','collision_mask'),
                    ('Initial VX (pixels/s)','velocity_x'),('Initial VY (pixels/s)','velocity_y'),
                    ('Gravity (pixels/s²)','gravity'),('Friction (pixels/s²)','friction')]:
                field(title,key)
            ttk.Label(self.inspector,text='Lua: self.vx, self.vy, self.grounded; OnCollisionEnter(other)',
                      style='Muted.TLabel',wraplength=225).pack(anchor='w',pady=5)
            ttk.Label(self.inspector, text="Screen", style="Muted.TLabel").pack(anchor="w", pady=(7,0))
            screen_var = tk.StringVar(value=obj["screen"])
            box = ttk.Combobox(self.inspector, state="readonly", textvariable=screen_var,
                               values=["bottom"] if self.project["mode"]=="3d2d" else ["top", "bottom"])
            box.pack(fill="x")
            def change_screen(event=None):
                old = obj["screen"]
                obj["screen"] = screen_var.get()
                try: clean_project(self.project)
                except ValueError as exc:
                    obj["screen"] = old
                    screen_var.set(old)
                    messagebox.showerror("Invalid screen", str(exc))
                    return
                self._refresh_scene_tree()
                self._note_changed()
            box.bind("<<ComboboxSelected>>", change_screen)
            controlled = tk.BooleanVar(value=obj["controllable"])
            def toggle():
                obj["controllable"] = controlled.get()
                self._note_changed()
            ttk.Checkbutton(self.inspector, text="Controllable with D-pad", variable=controlled,
                            command=toggle).pack(anchor="w", pady=9)
            ttk.Label(self.inspector, text="Sprite image", style="Muted.TLabel").pack(anchor="w", pady=(7,0))
            asset_var = tk.StringVar(value=obj['asset'])
            asset_select = ttk.Combobox(self.inspector, state="readonly", textvariable=asset_var,
                                       values=list(self.project['assets']))
            asset_select.pack(fill="x", pady=3)
            def change_asset(_=None):
                obj['asset'] = asset_var.get()
                obj['frame'] = 0
                self._note_changed()
            asset_select.bind('<<ComboboxSelected>>', change_asset)
            ttk.Button(self.inspector, text="Import PNG and assign", command=self.import_png).pack(fill="x", pady=(7,0))
            ttk.Button(self.inspector, text="Import PNG animation sheet", command=lambda:self.import_png(sheet=True)).pack(fill="x", pady=(3,0))
        if obj['type'] in ('Cube3D','Mesh3D'):
            ttk.Button(self.inspector, text="🎨 Pick color", command=self._pick_object_color).pack(fill="x", pady=(10,0))

    def attach_script(self):
        obj=self._find_object()
        if obj is None:return
        if self.project_path is None and not self.save_as():return
        file=filedialog.askopenfilename(title="Attach a .lua script in project folder",
               initialdir=str(self.project_path.parent),filetypes=[("Lua scripts","*.lua")])
        if not file:return
        try:
            relative=Path(file).resolve().relative_to(self.project_path.parent.resolve()).as_posix()
            validate_script(Path(file).read_text(encoding="utf-8"))
            old=obj.get('script','');obj['script']=relative
            clean_project(self.project)
        except (ValueError,OSError,UnicodeError) as exc:
            obj['script']=old if 'old' in locals() else obj.get('script','')
            messagebox.showerror("Cannot attach script",str(exc));return
        self._show_inspector();self._note_changed()
        self._log(f"Script attached: {relative}")

    def remove_script(self):
        obj=self._find_object()
        if obj and obj.get('script'):
            obj['script']='';self._show_inspector();self._note_changed()

    def edit_script(self):
        obj=self._find_object()
        if obj is None:return
        if self.project_path is None and not self.save_as():return
        relative=obj.get('script') or f"scripts/object_{obj['id']}.lua"
        try:
            path=script_path(relative,self.project_path.parent) if obj.get('script') else self.project_path.parent/relative
            initial=path.read_text(encoding="utf-8") if path.exists() else (
                'function Update(dt)\n    self.angle = self.angle + 90 * dt\nend\n'
                if obj['type'] in ('Cube3D','Mesh3D') else
                'function Update(dt)\n    if Input.IsDown("RIGHT") then\n'
                '        self.x = self.x + 80 * dt\n    end\nend\n')
        except (OSError,ValueError,UnicodeError) as exc:
            messagebox.showerror('Script unavailable',str(exc));return
        win=tk.Toplevel(self.root);win.title('Script: '+relative)
        win.geometry('720x520');win.configure(bg=DARK)
        tk.Label(win,text='Lua 5.4  •  locals, tables, functions, loops; Start(), Update(dt), self, Input, Scene',
                 fg=SOFT,bg=DARK,font=('Consolas',10)).pack(fill='x',padx=10,pady=(12,4))
        bottom=ttk.Frame(win,padding=10);bottom.pack(side='bottom',fill='x')
        area=ScrolledText(win,wrap='none',font=('Consolas',12),bg='#101926',fg=TEXT,
                           insertbackground='white',undo=True)
        area.pack(side='top',fill='both',expand=True,padx=10,pady=4)
        area.insert('1.0',initial)
        status=ttk.Label(bottom,text='Syntax check uses installed Lua when available; otherwise ROM checks at runtime.')
        status.pack(side='left')
        def save_text():
            try:
                code=area.get('1.0','end-1c')
                validation=validate_script(code)
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(code+'\n',encoding='utf-8')
                obj['script']=relative
                self._show_inspector();self._note_changed()
                self._log(f"Script saved: {relative} ({validation})")
                win.destroy()
            except (OSError,ValueError) as exc:
                messagebox.showerror('Script not saved',str(exc),parent=win)
        ttk.Button(bottom,text='Save Script',command=save_text).pack(side='right')
        ttk.Button(bottom,text='Cancel',command=win.destroy).pack(side='right',padx=8)

    def _resize_preview(self, event):
        self.scale = max(0.35, min(1.65, (event.height - 108) / (preview.H * 2),
                                     (event.width - 46) / preview.W))
        self._redraw()

    def _redraw(self):
        secs = (time.perf_counter()-self.start_time) if self.animating else 0
        preview.draw(self.canvas, self.project, self.selected_id, secs, self.scale,
                     self.project_path.parent if self.project_path else None)

    def _animate(self):
        try:
            if self.animating: self._redraw()
            self.root.after(50, self._animate)
        except tk.TclError:
            pass

    def toggle_pause(self):
        self.animating = not self.animating
        self.pause_btn.configure(text="⏸ Pause" if self.animating else "▶ Animate")
        self.start_time = time.perf_counter()
        self._redraw()

    def _canvas_click(self, event):
        self.canvas.focus_set()
        current = self.canvas.find_withtag("current")
        if not current:
            return
        for tag in self.canvas.gettags(current[0]):
            if tag.startswith("object:"):
                self.selected_id = int(tag.split(":",1)[1])
                self._refresh_scene_tree()
                self._show_inspector()
                self._redraw()
                self.last_drag = (event.x, event.y)
                break

    def _canvas_drag(self, event):
        if self.last_drag is None: return
        obj = self._find_object()
        if not obj: return
        dx = event.x-self.last_drag[0]
        dy = event.y-self.last_drag[1]
        if obj["type"] == "Sprite2D":
            obj["x"] = max(0, min(248, round(obj["x"] + dx/self.scale)))
            obj["y"] = max(0, min(184, round(obj["y"] + dy/self.scale)))
        else:
            obj["x"] = max(-20, min(20, round(obj["x"]+dx/57,2)))
            obj["y"] = max(-20, min(20, round(obj["y"]-dy/57,2)))
        self.last_drag = (event.x, event.y)
        self._note_changed()
        self._show_inspector()

    def _canvas_key(self, event):
        obj = self._find_object()
        if not obj or obj["type"] != "Sprite2D": return
        deltas = {"Left":(-1,0), "Right":(1,0), "Up":(0,-1), "Down":(0,1)}
        if event.keysym not in deltas: return
        dx,dy = deltas[event.keysym]
        obj["x"] = max(0,min(240, obj["x"]+dx*obj["speed"]))
        obj["y"] = max(0,min(176, obj["y"]+dy*obj["speed"]))
        self._note_changed()
        self._show_inspector()

    def _delete_shortcut(self, _):
        if self.root.focus_get() == self.tree or self.root.focus_get() == self.canvas:
            self.delete_selected()

    def add_cube(self):
        if self.project["mode"] not in ("3d2d","dual3d"):
            messagebox.showinfo("2D mode", "Switch to a 3D mode to add a cube.")
            return
        obj = {"id": next_object_id(self.project), "type":"Cube3D", "name":"Cube",
               "scene":self.project["active_scene"],
               "screen":"top", "x":0, "y":0, "z":0, "size":1.2, "spin":0.7, "color":"#7BC3DF"}
        self._add(obj)

    def import_obj(self):
        if self.project['mode'] not in ('3d2d','dual3d'):
            messagebox.showinfo('3D mode','Select a 3D mode to import models.')
            return
        if self.project_path is None and not self.save_as():return
        filename=filedialog.askopenfilename(title='Import OBJ mesh',filetypes=[('Wavefront OBJ','*.obj')])
        if not filename:return
        try:
            from .meshassets import parse_obj,simplify,MAX_EXPORT_FACES
            model=parse_obj(filename)
            target=0
            if len(model.triangles)>MAX_EXPORT_FACES:
                target=simpledialog.askinteger('Simplify Model',f'OBJ has {len(model.triangles)} triangles.\nTarget triangle budget (4..1800):',initialvalue=min(900,MAX_EXPORT_FACES),minvalue=4,maxvalue=MAX_EXPORT_FACES,parent=self.root)
                if target is None:return
            base=self.project_path.parent
            mesh_dir=base/'models';mesh_dir.mkdir(exist_ok=True)
            key=__import__('re').sub(r'[^a-z0-9_]', '_', Path(filename).stem.lower())[:35]
            if not key or key[0].isdigit():key='mesh_'+key
            root_key=key;num=2
            while key in self.project.setdefault('mesh_assets',{}):
                key=f'{root_key}_{num}';num+=1
            import re
            # OBJ and its MTL stay together; copied MTL names preserve usemtl colors.
            dest=mesh_dir/(key+'.obj')
            original=Path(filename).resolve()
            text=original.read_text(encoding='utf-8-sig',errors='replace')
            mtl_lines=[]
            for raw in text.splitlines():
                parts=raw.strip().split()
                if parts and parts[0]=='mtllib':
                    for lib in parts[1:]:
                        source=(original.parent/lib).resolve()
                        if source.is_relative_to(original.parent) and source.is_file():
                            name=key+'_'+source.name
                            # Rewrite material texture references to unique copied PNG names.
                            if source.is_file():
                                mtl_content=[]
                                for mrow in source.read_text(encoding='utf-8',errors='replace').splitlines():
                                    mc=mrow.split('#',1)[0].split()
                                    if mc and mc[0]=='map_Kd' and len(mc)>=2:
                                        rel=' '.join(mc[1:]);picture=(source.parent/rel).resolve()
                                        if (picture.is_relative_to(original.parent) and picture.is_file() and
                                                picture.suffix.lower()=='.png'):
                                            from .texassets import convert_texture
                                            convert_texture(picture)
                                            image_name=key+'_'+picture.name
                                            if picture.resolve()!=(mesh_dir/image_name).resolve():
                                                shutil.copyfile(picture,mesh_dir/image_name)
                                            mrow='map_Kd '+image_name
                                    mtl_content.append(mrow)
                                (mesh_dir/name).write_text('\n'.join(mtl_content)+'\n',encoding='utf-8')
                            mtl_lines.append('mtllib '+name)
                else:mtl_lines.append(raw)
            dest.write_text('\n'.join(mtl_lines)+'\n',encoding='utf-8')
            self.project['mesh_assets'][key]={'path':f'models/{key}.obj','target_triangles':target}
            obj={'id':next_object_id(self.project),'type':'Mesh3D','name':key,'screen':'top',
                 'scene':self.project['active_scene'],'x':0,'y':0,'z':0,'size':1.8,
                 'spin':0.0,'rot_x':0,'rot_y':0,'rot_z':0,'mesh':key,'color':'#E8B77D'}
            self.project['objects'].append(obj)
            clean_project(self.project)
            self.selected_id=obj['id'];self._refresh_scene_tree();self._show_inspector();self._note_changed()
            self._log(f'Imported OBJ {key}: {len(model.triangles)} triangles, target {target or "original"}')
        except (ValueError,OSError) as err:
            messagebox.showerror('OBJ import failed',str(err))

    def assign_mesh_texture(self):
        obj=self._find_object()
        if not obj or obj['type']!='Mesh3D':return
        if self.project_path is None and not self.save_as():return
        file=filedialog.askopenfilename(title='Assign PNG texture to OBJ UVs',filetypes=[('PNG texture','*.png')])
        if not file:return
        try:
            from .texassets import convert_texture
            convert_texture(file)
            model_dir=self.project_path.parent/'models';model_dir.mkdir(exist_ok=True)
            target=model_dir/f'{obj["mesh"]}_override.png'
            if Path(file).resolve()!=target.resolve():shutil.copyfile(file,target)
            self.project['mesh_assets'][obj['mesh']]['texture']=f'models/{target.name}'
            self._note_changed();self._show_inspector();self._redraw()
            self._log(f'{obj["mesh"]}: override texture {target.name}')
        except (ValueError,OSError) as err:messagebox.showerror('Texture import failed',str(err))

    def clear_mesh_texture(self):
        obj=self._find_object()
        if not obj or obj['type']!='Mesh3D':return
        self.project['mesh_assets'][obj['mesh']]['texture']=''
        self._note_changed();self._show_inspector();self._redraw()

    def set_mesh_lod(self):
        obj=self._find_object()
        if not obj or obj['type']!='Mesh3D':return
        asset=self.project['mesh_assets'][obj['mesh']]
        try:
            from .meshassets import parse_obj
            base=self.project_path.parent if self.project_path else Path.cwd()
            model=parse_obj(base/asset['path'])
            total=min(len(model.triangles),asset.get('target_triangles') or 1800)
            initial=asset.get('lod_triangles') or max(4,total//3)
            value=simpledialog.askinteger('Automatic LOD',
                f'High detail: up to {total} triangles.\nLow detail target (0 disables LOD):',
                initialvalue=initial,minvalue=0,maxvalue=max(4,total-1),parent=self.root)
            if value is None:return
            if value not in (0,) and value<4:raise ValueError('LOD minimum is 4 triangles')
            asset['lod_triangles']=value
            self._note_changed()
        except (ValueError,OSError) as err:messagebox.showerror('LOD',str(err))

    def simplify_obj(self):
        obj=self._find_object()
        if not obj or obj['type']!='Mesh3D':
            messagebox.showinfo('Simplify Model','Select a Mesh3D object first.');return
        from .meshassets import parse_obj,simplify
        key=obj['mesh'];info=self.project['mesh_assets'][key]
        try:
            mesh=parse_obj(self.project_path.parent/info['path'])
            current=len(mesh.triangles)
            goal=simpledialog.askinteger('Simplify Model — QEM',
                f'Imported model: {current} triangles\nTarget triangles (0 = keep original):',
                initialvalue=info['target_triangles'] or min(current,900),minvalue=0,maxvalue=1800,parent=self.root)
            if goal is None:return
            if goal and goal<4:raise ValueError('Minimum target is 4 triangles')
            reduced=simplify(mesh,goal) if goal and goal<current else mesh
            info['target_triangles']=goal
            self._note_changed();self._redraw()
            self._log(f'{key}: {current} → {len(reduced.triangles)} triangles (target {goal or "original"})')
            messagebox.showinfo('Simplify Model',f'{current} → {len(reduced.triangles)} triangles\n'
               'Original OBJ is preserved. Reduction is applied at export.')
        except (OSError,ValueError) as exc:messagebox.showerror('Simplification failed',str(exc))

    def edit_project_properties(self):
        """Edit project-level metadata and the three short NDS banner lines."""
        dialog=tk.Toplevel(self.root)
        dialog.title('Project Properties — NDS Banner')
        dialog.transient(self.root)
        dialog.resizable(True,True)
        dialog.geometry('460x490')
        defaults=self.project.get('metadata',{})
        fields={}
        rows=[('Project name','name',70),('Description','description',500),('Project author','author',100),
              ('NDS title (12 ASCII)','banner_title',12),('NDS subtitle (12 ASCII)','banner_subtitle',12),
              ('NDS creator (12 ASCII)','banner_creator',12),('Icon PNG (32×32)','icon',180)]
        panel=ttk.Frame(dialog,padding=12);panel.pack(fill='both',expand=True)
        for title,key,limit in rows:
            ttk.Label(panel,text=title).pack(anchor='w',pady=(5,0))
            row=ttk.Frame(panel);row.pack(fill='x')
            var=tk.StringVar(value=self.project['name'] if key=='name' else defaults.get(key,''))
            ent=ttk.Entry(row,textvariable=var);ent.pack(side='left',fill='x',expand=True)
            fields[key]=var
            if key=='icon':
                def pick():
                    path=filedialog.askopenfilename(title='Choose a 32x32 PNG icon',filetypes=[('PNG files','*.png')],parent=dialog)
                    if not path:return
                    if self.project_path is None and not self.save_as():return
                    from .compiler import slug
                    import shutil
                    base=self.project_path.parent if self.project_path else Path.cwd()
                    target=base/'assets'/('banner_'+slug(Path(path).stem)+'.png')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if Path(path).resolve()!=target.resolve():shutil.copyfile(path,target)
                    var.set(target.relative_to(base).as_posix())
                ttk.Button(row,text='Browse...',command=pick).pack(side='left',padx=(5,0))
        ttk.Label(panel,text='NDS banner text is three 12-character ASCII lines.\nThe full description/author remain in the project JSON.',style='Muted.TLabel').pack(anchor='w',pady=8)
        def save_values():
            old=deepcopy(self.project)
            self.project['name']=fields['name'].get()
            self.project['metadata']={k:fields[k].get() for _,k,_ in rows if k!='name'}
            try:clean_project(self.project)
            except (ValueError,OSError) as exc:
                self.project=old
                messagebox.showerror('Project Properties',str(exc),parent=dialog)
                return
            self.project_name.delete(0,'end');self.project_name.insert(0,self.project['name'])
            self._note_changed();dialog.destroy()
        ttk.Button(panel,text='Save properties',command=save_values).pack(fill='x',pady=8)

    def edit_camera_3d(self,bottom=False):
        if self.project['mode'] not in ('3d2d','dual3d'):return
        if bottom and self.project['mode']!='dual3d':return
        dialog=tk.Toplevel(self.root);dialog.title('Bottom 3D Camera' if bottom else 'Top 3D Camera');dialog.transient(self.root)
        dialog.geometry('340x360')
        camera=self.project.setdefault('camera_bottom3d' if bottom else 'camera_3d',{'x':0,'y':0,'z':5,'yaw':0,'pitch':0,'fov':65})
        entries={}
        for key in ('x','y','z','yaw','pitch','fov'):
            row=ttk.Frame(dialog,padding=(12,3));row.pack(fill='x')
            ttk.Label(row,text=key.upper(),width=9).pack(side='left')
            entry=ttk.Entry(row);entry.insert(0,str(camera[key]));entry.pack(side='left',fill='x',expand=True)
            entries[key]=entry
        def apply():
            prev=dict(camera)
            try:
                camera.update({key:float(entry.get()) for key,entry in entries.items()})
                clean_project(self.project)
            except ValueError as e:
                camera.clear();camera.update(prev);messagebox.showerror('Camera',str(e));return
            self._note_changed();dialog.destroy()
        ttk.Button(dialog,text='Save camera',command=apply).pack(pady=12)

    def edit_render_3d(self):
        camera=self.project['camera_3d']
        dialog=tk.Toplevel(self.root);dialog.title('3D Rendering & Performance');dialog.transient(self.root)
        dialog.geometry('360x380');dialog.resizable(False,False)
        switches={}
        for key,label in [('frustum_culling','Frustum culling (skip off-screen meshes)'),
                          ('fog_enabled','Enable hardware distance fog'),
                          ('profiler','Show profiler when SELECT is held')]:
            v=tk.BooleanVar(value=camera.get(key,key=='frustum_culling'))
            switches[key]=v;ttk.Checkbutton(dialog,text=label,variable=v).pack(anchor='w',padx=12,pady=7)
        fields={}
        for key,label,default in [('fog_color','Fog RGB color (#RRGGBB)','#62799B'),
                                  ('fog_strength','Fog intensity (0..1)',0.65),
                                  ('brightness','Baked material brightness (0.2..2)',1.0)]:
            ttk.Label(dialog,text=label).pack(anchor='w',padx=12)
            e=ttk.Entry(dialog);e.insert(0,str(camera.get(key,default)));e.pack(fill='x',padx=12,pady=(1,8));fields[key]=e
        def apply():
            updated=dict(camera)
            for key,var in switches.items():updated[key]=var.get()
            try:
                updated['fog_color']=fields['fog_color'].get().strip()
                updated['fog_strength']=float(fields['fog_strength'].get())
                updated['brightness']=float(fields['brightness'].get())
                changed=dict(self.project);changed['camera_3d']=updated
                clean_project(changed)
            except (ValueError,TypeError) as exc:
                messagebox.showerror('Invalid rendering settings',str(exc),parent=dialog);return
            self.project['camera_3d']=updated;self._note_changed();dialog.destroy()
        ttk.Button(dialog,text='Apply',command=apply).pack(pady=8)

    def add_sprite(self):
        obj = {"id": next_object_id(self.project), "type":"Sprite2D", "name":"Sprite",
               "scene":self.project["active_scene"],
               "screen":"bottom", "x":110, "y":95, "speed":2, "controllable":False,
               "asset":next(iter(self.project['assets'])), "color":"#FFFFFF"}
        self._add(obj)

    def import_png(self, sheet=False):
        # Saving first gives imported files a stable project-relative directory.
        if self.project_path is None and not self.save_as():
            return
        path = filedialog.askopenfilename(title="Import a hardware OBJ PNG",
                    filetypes=[("PNG sprite", "*.png")])
        if not path: return
        before = deepcopy(self.project)
        try:
            from .pngassets import convert_png, convert_sprite_sheet
            dims={}
            if sheet:
                fw=simpledialog.askinteger('Sprite sheet','Frame width (8, 16, 32, 64)?',
                      parent=self.root,minvalue=8,maxvalue=64)
                if fw is None:return
                fh=simpledialog.askinteger('Sprite sheet','Frame height (8, 16, 32, 64)?',
                      parent=self.root,minvalue=8,maxvalue=64)
                if fh is None:return
                frames=convert_sprite_sheet(path,fw,fh)
                dims={'frame_width':fw,'frame_height':fh}
                result=frames[0]
            else:
                result=convert_png(path)
            # Keep assets inside the saved project directory; no absolute paths in JSON.
            assets_dir=self.project_path.parent/'assets'
            assets_dir.mkdir(exist_ok=True)
            stem=slug(Path(path).stem).lower() or 'sprite'
            ident=stem
            num=2
            while ident in self.project['assets']:
                ident=f'{stem}_{num}';num+=1
            target=assets_dir/(ident+'.png')
            # Avoid overwriting a PNG currently in use by another asset.
            if Path(path).resolve()!=target.resolve():
                shutil.copyfile(path,target)
            self.project['assets'][ident]={'path':f'assets/{ident}.png',**dims}
            selected=self._find_object()
            if selected and selected['type']=='Sprite2D':
                selected['asset']=ident
                selected['frame']=0
                if sheet and selected.get('fps',0)==0:selected['fps']=6
            else:
                obj={"id":next_object_id(self.project), "type":"Sprite2D", "name":ident,
                     "screen":"bottom", "x":100, "y":90, "speed":2,
                     "controllable":False,"asset":ident,"color":"#FFFFFF"}
                self.project['objects'].append(obj)
                if sheet:obj['fps']=6
                self.selected_id=obj['id']
            clean_project(self.project)
            self._refresh_scene_tree()
            self._show_inspector()
            self._note_changed()
            self._log(f'Imported {Path(path).name}: {result.width}x{result.height}' + (f' x {len(frames)} frames' if sheet else '') + f' -> {ident} '
                      + ('(quantized to <=15 colors)' if result.reduced_colors else '(<=15 colors)'))
        except (OSError,ValueError) as exc:
            self.project=before
            self._refresh_scene_tree()
            self._show_inspector()
            self._redraw()
            messagebox.showerror('PNG import failed',str(exc))

    def create_scene(self):
        name=simpledialog.askstring('Create scene','Scene name (letters, digits, underscores):',parent=self.root)
        if not name:return
        before=deepcopy(self.project)
        self.project.setdefault('scenes',['Main']).append(name)
        try:clean_project(self.project)
        except ValueError as err:
            self.project=before;messagebox.showerror('Invalid scene',str(err));return
        self.project['active_scene']=name
        self._note_changed();self._refresh_scene_tree();self._show_inspector()
        self._log(f'Created scene {name}; add objects and assign them via the inspector.')

    def select_scene(self):
        scenes=self.project.get('scenes',['Main'])
        name=simpledialog.askstring('Preview scene',
            'Select scene name: '+', '.join(scenes),initialvalue=self.project.get('active_scene','Main'),parent=self.root)
        if not name:return
        if name not in scenes:
            messagebox.showerror('Scene','Unknown scene');return
        self.project['active_scene']=name
        self._note_changed();self._redraw();self._log('Preview scene set to '+name)

    def import_wav(self):
        from .wavassets import convert_wav
        if self.project_path is None and not self.save_as():return
        filename=filedialog.askopenfilename(title='Import PCM WAV',filetypes=[('WAV audio','*.wav')])
        if not filename:return
        base=self.project_path.parent
        ident=Path(filename).stem.replace('-','_').replace(' ','_')
        import re
        ident=re.sub('[^A-Za-z0-9_]','_',ident)
        if not ident or ident[0].isdigit():ident='sound_'+ident
        if ident in self.project.get('sounds',{}):
            messagebox.showerror('Sound ID','A sound with that name already exists');return
        try:
            pcm,frames,rate=convert_wav(filename)
            dest=base/'sounds'/f'{ident}.wav'
            dest.parent.mkdir(parents=True,exist_ok=True)
            if Path(filename).resolve()!=dest.resolve():shutil.copyfile(filename,dest)
            sounds=self.project.setdefault('sounds',{})
            sounds[ident]={'path':f'sounds/{ident}.wav'}
            try:clean_project(self.project)
            except ValueError:
                del sounds[ident];raise
            self._note_changed();self._log(f'Imported Audio.play("{ident}"): {frames} samples at {rate} Hz')
        except (OSError,ValueError) as err:messagebox.showerror('Import WAV failed',str(err))

    def show_budget(self):
        from .compiler import asset_conversion,background_conversion,script_conversion
        from .wavassets import convert_wav
        from .budget import estimate_budget
        base=self.project_path.parent if self.project_path else Path.cwd()
        try:
            p=clean_project(self.project)
            sounds={k:convert_wav(base/info['path']) for k,info in p['sounds'].items()}
            report=estimate_budget(p,asset_conversion(p,base),background_conversion(p,base),sounds,script_conversion(p,base))
            from .compiler import mesh_conversion
            for key,info in mesh_conversion(p,base).items():
                verts,faces=info['packed']
                report+=f'\n3D {key}: {len(verts)} vertices / {len(faces)} triangles; {len(verts)*6+len(faces)*8} bytes' 
            messagebox.showinfo('NovaDS hardware budget',report)
        except (ValueError,OSError) as err:messagebox.showerror('Hardware budget',str(err))

    def _add(self, obj):
        self.project["objects"].append(obj)
        try: clean_project(self.project)
        except ValueError as exc:
            self.project["objects"].pop()
            messagebox.showerror("Scene limit", str(exc))
            return
        self.selected_id = obj["id"]
        self._refresh_scene_tree()
        self._show_inspector()
        self._note_changed()

    def delete_selected(self):
        if self.selected_id is None: return
        self.project["objects"] = [o for o in self.project["objects"] if o["id"] != self.selected_id]
        self.selected_id = self.project["objects"][0]["id"] if self.project["objects"] else None
        self._refresh_scene_tree()
        self._show_inspector()
        self._note_changed()

    def _apply_project_name(self, _=None):
        value = self.project_name.get().strip()[:70] or "Untitled"
        if value != self.project["name"]:
            self.project["name"] = value
            self._note_changed()
        self.project_name.delete(0,"end")
        self.project_name.insert(0,value)

    def _change_mode(self, _=None):
        old, new = self.project["mode"], self.mode_var.get()
        if old == new: return
        previous=deepcopy(self.project)
        if new == "2d2d":
            cubes = sum(obj["type"] in ("Cube3D","Mesh3D") for obj in self.project["objects"])
            if cubes and not messagebox.askyesno("Change mode", f"Switching to 2D removes {cubes} 3D object(s). Continue?"):
                self.mode_var.set(old)
                return
            self.project["objects"] = [o for o in self.project["objects"] if o["type"] not in ("Cube3D","Mesh3D")]
        elif new=='3d2d':
            if old=='dual3d':
                for obj in self.project['objects']:
                    if obj['type'] in ('Cube3D','Mesh3D'): obj['screen']='top'
            else:
                for obj in self.project['objects']:
                    if obj['screen']=='top':obj['screen']='bottom'
        elif new=='dual3d':
            if any(o['type']=='Sprite2D' for o in self.project['objects']) or self.project.get('background_layers'):
                if not messagebox.askyesno('Switch to Dual 3D','Dual 3D reserves the 2D video layers. Remove 2D sprites and backgrounds?'):
                    self.mode_var.set(old);return
                self.project['objects']=[o for o in self.project['objects'] if o['type']!='Sprite2D']
                self.project['background_layers']={};self.project['extra_background_layers']={}
        self.project["mode"] = new
        if new in ('3d2d','dual3d'):
            self.project.setdefault('background_layers',{}).pop('top',None)
            self.project.setdefault('extra_background_layers',{}).pop('top',None)
            self.project.setdefault('camera_follow',{}).pop('top',None)
        try: clean_project(self.project)
        except ValueError as exc:
            messagebox.showerror("Cannot switch modes", str(exc))
            self.project = previous
            self.mode_var.set(old)
            return
        self.mode_help.configure(text=FORMATS[new])
        self.selected_id = self.project["objects"][0]["id"] if self.project["objects"] else None
        self._refresh_scene_tree()
        self._show_inspector()
        self._note_changed()

    def _pick_background(self, screen):
        key = "background_"+screen
        value = colorchooser.askcolor(initialcolor=self.project[key], title=f"{screen.title()} backdrop")[1]
        if value:
            self.project[key] = value
            self._note_changed()

    def paint_tilemap(self,screen,slot=0):
        if self.project['mode']=='dual3d' or (screen=='top' and self.project['mode']=='3d2d'):
            messagebox.showinfo('Top screen','Switch to 2D+2D for top tilemap editing.');return
        if self.project_path is None and not self.save_as():return
        try:
            from .tilepainter import TilePainter
            TilePainter(self,screen,slot)
        except (ValueError,OSError) as exc:messagebox.showerror('Tilemap Painter',str(exc))

    def edit_camera_follow(self):
        win=tk.Toplevel(self.root);win.title('Camera follow targets');win.transient(self.root)
        win.geometry('360x240')
        outer=ttk.Frame(win,padding=18);outer.pack(fill='both',expand=True)
        options={screen:[(f"{o['name']} (ID {o['id']})",o['id']) for o in self.project['objects']
                        if o['type']=='Sprite2D' and o['screen']==screen] for screen in ('top','bottom')}
        values={}
        for screen in ('top','bottom'):
            ttk.Label(outer,text=f'{screen.upper()} CAMERA').pack(anchor='w',pady=(7,2))
            labels=['No follow (fixed camera)']+[a for a,_ in options[screen]]
            found=self.project.get('camera_follow',{}).get(screen,0)
            current=next((i+1 for i,(_,oid) in enumerate(options[screen]) if oid==found),0)
            var=tk.StringVar(value=labels[current]);values[screen]=(var,labels)
            ttk.Combobox(outer,values=labels,textvariable=var,state='readonly').pack(fill='x')
        def save():
            target={}
            for screen in ('top','bottom'):
                var,labels=values[screen]
                i=labels.index(var.get())
                if i:target[screen]=options[screen][i-1][1]
            project=deepcopy(self.project);project['camera_follow']=target
            try:self.project=clean_project(project);self._note_changed();win.destroy()
            except ValueError as exc:messagebox.showerror('Camera',str(exc),parent=win)
        ttk.Button(outer,text='Save camera settings',command=save).pack(pady=12)

    def edit_background(self,screen,slot=0):
        """Import/edit one 256x256 4bpp BG on a 2D display."""
        if self.project['mode']=='dual3d' or (screen=='top' and self.project['mode']=='3d2d'):
            messagebox.showinfo('3D screen', 'The top screen is the 3D renderer. Switch to 2D+2D for a top tile layer.')
            return
        dialog=tk.Toplevel(self.root)
        dialog.title(f'{screen.title()} BG{2+slot} hardware tile background')
        dialog.geometry(f'430x{min(450,max(350,self.root.winfo_screenheight()-130))}')
        dialog.minsize(345,300)
        dialog.transient(self.root)
        layer=(self.project.get('background_layers',{}).get(screen,{}) if slot==0 else
               (self.project.get('extra_background_layers',{}).get(screen) or [{}])[0])
        if layer.get('tilemap'):
            messagebox.showinfo('Painted Tilemap','Use the Tilemap Painter to edit painted layers.',parent=dialog)
            dialog.destroy();return
        namevar=tk.StringVar(value=layer.get('name',f'layer{slot}'))
        parallax=tk.StringVar(value=str(layer.get('parallax',1)))
        pathvar=tk.StringVar(value=layer.get('path',''))
        scrollx=tk.StringVar(value=str(layer.get('scroll_x',0)))
        scrolly=tk.StringVar(value=str(layer.get('scroll_y',0)))
        affine=tk.BooleanVar(value=bool(layer.get('affine',False)))
        angle=tk.StringVar(value=str(layer.get('angle',0)))
        scale=tk.StringVar(value=str(layer.get('scale',1)))
        outer=ttk.Frame(dialog,padding=14)
        outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='256x256 PNG  •  max 15 colors + transparency').pack(anchor='w')
        ttk.Label(outer,textvariable=pathvar,wraplength=355).pack(anchor='w',pady=(4,8))
        def import_bg():
            if self.project_path is None and not self.save_as():return
            filename=filedialog.askopenfilename(title='Import 256x256 PNG tile background',filetypes=[('PNG image','*.png')],parent=dialog)
            if not filename:return
            try:
                from .bgassets import convert_background
                result=convert_background(filename, affine=bool(affine.get()))
                directory=self.project_path.parent/'assets'
                directory.mkdir(parents=True,exist_ok=True)
                target=directory/f'bg_{screen}{slot}.png'
                if Path(filename).resolve()!=target.resolve():shutil.copyfile(filename,target)
                pathvar.set('assets/'+target.name)
                self._log(f'{screen.title()} BG: {result.unique_tiles} unique tiles / 256')
            except (OSError,ValueError) as exc:
                messagebox.showerror('Cannot import background',str(exc),parent=dialog)
        ttk.Button(outer,text='Import / Replace PNG...',command=import_bg).pack(anchor='w',pady=(0,8))
        fields=ttk.Frame(outer)
        fields.pack(fill='x')
        for i,(name,var) in enumerate([('Scroll X',scrollx),('Scroll Y',scrolly),('Angle °',angle),('Scale',scale)]):
            ttk.Label(fields,text=name).grid(row=i//2*2,column=i%2,padx=(0,10),sticky='w')
            ttk.Entry(fields,textvariable=var,width=12).grid(row=i//2*2+1,column=i%2,padx=(0,10),pady=(0,7),sticky='w')
        ttk.Checkbutton(outer,text='Hardware affine (BG2, only layer on screen)',variable=affine).pack(anchor='w')
        details=ttk.Frame(outer);details.pack(fill='x',pady=(4,0))
        ttk.Label(details,text='Name').pack(side='left')
        ttk.Entry(details,textvariable=namevar,width=12).pack(side='left',padx=4)
        ttk.Label(details,text='Parallax').pack(side='left')
        ttk.Entry(details,textvariable=parallax,width=7).pack(side='left',padx=4)
        buttons=ttk.Frame(outer);buttons.pack(fill='x',side='bottom',pady=(12,0))
        def save():
            old=deepcopy(self.project)
            try:
                if pathvar.get():
                    updated={'name':namevar.get(),'parallax':float(parallax.get()),
                        'path':pathvar.get(),'scroll_x':float(scrollx.get()),'scroll_y':float(scrolly.get()),
                        'angle':float(angle.get()),'scale':float(scale.get()),'affine':affine.get()}
                    if slot==0:self.project.setdefault('background_layers',{})[screen]=updated
                    else:self.project.setdefault('extra_background_layers',{})[screen]=[updated]
                elif slot==0:self.project.setdefault('background_layers',{}).pop(screen,None)
                else:self.project.setdefault('extra_background_layers',{}).pop(screen,None)
                self.project=clean_project(self.project)
                self._note_changed();dialog.destroy()
            except (ValueError,TypeError) as exc:
                self.project=old
                messagebox.showerror('Background settings',str(exc),parent=dialog)
        def remove():
            pathvar.set('')
            save()
        ttk.Button(buttons,text='Save settings',command=save).pack(side='right')
        ttk.Button(buttons,text='Remove BG',command=remove).pack(side='left')
        ttk.Button(buttons,text='Cancel',command=dialog.destroy).pack(side='right',padx=6)

    def _pick_object_color(self):
        obj = self._find_object()
        if not obj: return
        value = colorchooser.askcolor(initialcolor=obj["color"], title=f"Color of {obj['name']}")[1]
        if value:
            obj["color"] = value
            self._note_changed()

    def _ok_to_discard(self):
        return not self.dirty or messagebox.askyesno("Unsaved changes", "Discard unsaved changes?")

    def new(self):
        if not self._ok_to_discard(): return
        self.project = new_project()
        self.project_path = None
        self.export_path = None
        self._project_loaded()
        self._log("New project created.")

    def open(self):
        if not self._ok_to_discard(): return
        path = filedialog.askopenfilename(title="Open NovaDS project", filetypes=[("NovaDS project", "*.novads.json"), ("JSON", "*.json")])
        if not path: return
        try:
            raw=json.loads(Path(path).read_text(encoding='utf-8'))
            if raw.get('version')==1:
                if not messagebox.askyesno('Migrate v0.1 project',
                    'This is a v0.1 project. Convert it to v0.5? '
                    'Existing sprites become the built-in Nova PNG. '
                    'Use Save As to preserve your old project.'):
                    return
                self.project=migrate_v1(raw)
            elif raw.get('version')==2:
                if not messagebox.askyesno('Upgrade v0.2 project',
                    'Upgrade this v0.2 project to v0.5?\nUse Save As to keep the original.'):
                    return
                self.project=migrate_v2(raw)
            elif raw.get('version')==3:
                if not messagebox.askyesno('Upgrade v0.3 project',
                    'Upgrade this v0.3 project to v0.5? The scripts will run as real Lua.\nUse Save As to preserve the old project.'):
                    return
                self.project=migrate_v3(raw)
            elif raw.get('version')==4:
                self.project=migrate_v4(raw)
                messagebox.showinfo('Project upgraded', 'v0.4 scene upgraded to v0.5. Save As to keep your original.')
            else:
                self.project=clean_project(raw)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Couldn't open project", str(exc))
            return
        self.project_path = Path(path)
        self.export_path = None
        self._project_loaded()
        self._log(f"Opened {path}")

    def save(self):
        if self.project_path is None:
            return self.save_as()
        self._apply_project_name()
        try: save_project(self.project_path, self.project)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Couldn't save project", str(exc))
            return False
        self.dirty = False
        self._update_title()
        self._log(f"Saved {self.project_path}")
        return True

    def save_as(self):
        path = filedialog.asksaveasfilename(title="Save NovaDS project", defaultextension=".novads.json",
                       initialfile=slug(self.project["name"])+".novads.json",
                       filetypes=[("NovaDS project", "*.novads.json")])
        if not path: return False
        new_path=Path(path)
        old_base=self.project_path.parent if self.project_path else None
        if old_base and old_base.resolve()!=new_path.parent.resolve():
            try:
                for key, asset in self.project['assets'].items():
                    if asset['path'].startswith(':builtin/'):
                        continue
                    src=asset_path(asset['path'],old_base)
                    dest=new_path.parent/'assets'/f'{key}.png'
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    if src.resolve()!=dest.resolve(): shutil.copyfile(src,dest)
                    asset['path']=f'assets/{key}.png'
                for key,layer in {**{f'{screen}0':v for screen,v in self.project.get('background_layers',{}).items()},
                                  **{f'{screen}1':items[0] for screen,items in self.project.get('extra_background_layers',{}).items() if items}}.items():
                    src=asset_path(layer['path'],old_base)
                    newrel=f'assets/bg_{key}.png'
                    dest=new_path.parent/newrel
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    if src.resolve()!=dest.resolve():shutil.copyfile(src,dest)
                    layer['path']=newrel
                for mesh_key,info in self.project.get('mesh_assets',{}).items():
                    src=(old_base/info['path']).resolve()
                    target=new_path.parent/'models'/f'{mesh_key}.obj'
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if src!=target.resolve():shutil.copyfile(src,target)
                    # Copy referenced model materials into the relocated project.
                    for raw in src.read_text(encoding='utf-8',errors='replace').splitlines():
                        parts=raw.strip().split()
                        if parts and parts[0]=='mtllib':
                            for lib in parts[1:]:
                                origin=(src.parent/lib).resolve();dest=(target.parent/lib).resolve()
                                if origin.is_relative_to(src.parent.resolve()) and origin.is_file() and dest.is_relative_to(target.parent.resolve()):
                                    dest.parent.mkdir(parents=True,exist_ok=True)
                                    if origin!=dest:shutil.copyfile(origin,dest)
                    if info.get('texture'):
                        text_src=asset_path(info['texture'],old_base)
                        tex_dest=new_path.parent/'models'/f'{mesh_key}_override.png'
                        if text_src.resolve()!=tex_dest.resolve():shutil.copyfile(text_src,tex_dest)
                        info['texture']=f'models/{mesh_key}_override.png'
                    # Relocate texture images embedded in material files.
                    for mtl in target.parent.glob(f'{mesh_key}_*.mtl'):
                        source_mtl=src.parent/mtl.name
                        if not source_mtl.is_file():continue
                        for row in source_mtl.read_text(encoding='utf-8',errors='replace').splitlines():
                            chunk=row.split('#',1)[0].split()
                            if chunk and chunk[0]=='map_Kd':
                                rel=' '.join(chunk[1:])
                                from_tex=(source_mtl.parent/rel).resolve()
                                to_tex=(mtl.parent/rel).resolve()
                                if from_tex.is_relative_to(src.parent.resolve()) and to_tex.is_relative_to(mtl.parent.resolve()) and from_tex.is_file():
                                    to_tex.parent.mkdir(parents=True,exist_ok=True)
                                    if from_tex!=to_tex:shutil.copyfile(from_tex,to_tex)
                    info['path']=f'models/{mesh_key}.obj'
                for sound_key,info in self.project.get('sounds',{}).items():
                    src=old_base/info['path']
                    target=new_path.parent/'sounds'/f'{sound_key}.wav'
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if src.resolve()!=target.resolve():shutil.copyfile(src,target)
                    info['path']=f'sounds/{sound_key}.wav'
                for obj in self.project['objects']:
                    if obj.get('script'):
                        src=script_path(obj['script'],old_base)
                        newrel=f"scripts/object_{obj['id']}.lua"
                        dest=new_path.parent/newrel
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        if src.resolve()!=dest.resolve():shutil.copyfile(src,dest)
                        obj['script']=newrel
            except OSError as exc:
                messagebox.showerror('Could not relocate project assets',str(exc))
                return False
        self.project_path = new_path
        return self.save()

    def export(self):
        self._apply_project_name()
        where = filedialog.askdirectory(title="Choose parent folder for DS source export")
        if not where: return False
        dest = Path(where) / ("NovaDS_"+slug(self.project["name"]))
        if dest.exists() and not messagebox.askyesno("Existing export", f"Update generated files in {dest.name}?"):
            return False
        try: export_to(dest, self.project, self.project_path.parent if self.project_path else Path.cwd())
        except (OSError, ValueError) as exc:
            messagebox.showerror("Export failed", str(exc))
            return False
        self.export_path = dest
        self._log(f"Exported devkitPro project to {dest}")
        messagebox.showinfo("Export complete", f"Generated project:\n{dest}\n\n"
                "Open it in devkitPro MSYS2 and run 'make', or click Build ROM.")
        return True

    @staticmethod
    def _msys_path(path):
        """Convert Windows filesystem paths into absolute MSYS2 paths."""
        path = Path(path).resolve().as_posix()
        if len(path) >= 2 and path[1] == ':':
            return '/' + path[0].lower() + path[2:]
        return path

    def _build_command(self):
        """Return a command that works without assuming the editor has MSYS2 env vars."""
        if os.name != 'nt':
            make = shutil.which('make')
            if not make:
                raise RuntimeError("GNU Make not found. Install a devkitPro build environment.")
            if not os.environ.get('DEVKITARM'):
                raise RuntimeError("DEVKITARM is not set. Run NovaDS from a devkitPro environment.")
            return [make, '--no-print-directory', '-C', str(self.export_path)]

        # devkitPro's MSYS2 bash is the most reliable Windows toolchain environment.
        bases = []
        if os.getenv('DEVKITPRO'):
            bases.append(Path(os.environ['DEVKITPRO']))
        bases.extend([Path('C:/devkitPro'), Path('C:/devkitpro')])
        seen = set()
        for base in bases:
            key = str(base).lower()
            if key in seen:
                continue
            seen.add(key)
            bash = base / 'msys2/usr/bin/bash.exe'
            if not bash.is_file():
                continue
            unix_root = self._msys_path(base)
            unix_dest = self._msys_path(self.export_path)
            # Preserve actual device path, including spaces; no cmd.exe quoting.
            # Pass development environment explicitly: Windows Explorer usually
            # does not have the environment variables that the MSYS2 terminal has.
            shell_command = (f'export DEVKITPRO={shlex.quote(unix_root)}; '
                f'export DEVKITARM="$DEVKITPRO/devkitARM"; '
                'export PATH="$DEVKITARM/bin:/usr/bin:$PATH"; '
                f'cd {shlex.quote(unix_dest)} || exit 1; '
                'echo "DEVKITARM=$DEVKITARM"; '
                'command -v make || exit 127; '
                'make --no-print-directory')
            return [str(bash), '-lc', shell_command]

        make = shutil.which('make')
        if make and os.getenv('DEVKITARM'):
            return [make, '--no-print-directory', '-C', str(self.export_path)]
        raise RuntimeError(
            'devkitPro MSYS2 was not found. Expected '
            'C:\\devkitPro\\msys2\\usr\\bin\\bash.exe. '
            'Install devkitPro or launch NovaDS from its MSYS2 shell.')

    def show_build_output(self):
        """A dedicated resizeable output window that fits smaller monitors."""
        if self.build_log_window is not None and self.build_log_window.winfo_exists():
            self.build_log_window.deiconify()
            self.build_log_window.lift()
            return self.build_log_window
        win = tk.Toplevel(self.root)
        win.title('NovaDS — Build Output')
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = min(960, max(500, sw - 110)), min(610, max(340, sh - 170))
        win.geometry(f'{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//2)}')
        win.minsize(min(460, sw), min(270, sh))
        win.configure(bg=DARK)
        toolbar = ttk.Frame(win, padding=8)
        toolbar.pack(fill='x')
        ttk.Label(toolbar, text='BUILD OUTPUT', foreground=ACCENT,
                  font=('Segoe UI', 11, 'bold')).pack(side='left', padx=(0,14))
        ttk.Button(toolbar, text='Copy Log', command=lambda: self._copy_build_log()).pack(side='left', padx=3)
        ttk.Button(toolbar, text='Save Log...', command=self._save_build_log).pack(side='left', padx=3)
        ttk.Button(toolbar, text='Clear', command=self._clear_build_log).pack(side='left', padx=3)
        self.build_log_text = ScrolledText(win, wrap='none', bg='#101926', fg='#DDE8F2',
                     insertbackground=TEXT, font=('Consolas', 10), relief='flat', undo=False)
        self.build_log_text.pack(fill='both', expand=True, padx=8, pady=(0,8))
        self.build_log_text.insert('1.0', ''.join(self.build_log_content))
        self.build_log_text.configure(state='disabled')
        self.build_log_window = win
        win.protocol('WM_DELETE_WINDOW', win.withdraw)
        return win

    def _append_build_output(self, value):
        # Invoked on the Tk main thread only, via _poll_build_events.
        self.build_log_content.append(value)
        if self.build_log_window is not None and self.build_log_window.winfo_exists():
            widget = self.build_log_text
            widget.configure(state='normal')
            widget.insert('end', value)
            widget.see('end')
            widget.configure(state='disabled')

    def _clear_build_log(self):
        if self.build_running:
            self._append_build_output('\n--- Log cleared while compilation continues ---\n')
        else:
            self.build_log_content.clear()
            if self.build_log_text:
                self.build_log_text.configure(state='normal')
                self.build_log_text.delete('1.0', 'end')
                self.build_log_text.configure(state='disabled')

    def _copy_build_log(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(''.join(self.build_log_content))
        self._log('Copied complete build log to clipboard')

    def _save_build_log(self):
        path = filedialog.asksaveasfilename(parent=self.build_log_window,
                  title='Save build output', initialfile='novads-build-log.txt',
                  defaultextension='.txt', filetypes=[('Text log', '*.txt'), ('All files', '*.*')])
        if path:
            try:
                Path(path).write_text(''.join(self.build_log_content), encoding='utf-8')
            except OSError as exc:
                messagebox.showerror('Could not save log', str(exc), parent=self.build_log_window)

    def _poll_build_events(self):
        """Read process output without freezing Tk or calling Tk from a worker."""
        try:
            while True:
                event, payload = self.build_events.get_nowait()
                if event == 'text':
                    self._append_build_output(payload)
                elif event == 'done':
                    code, failure = payload
                    rom = self.export_path / 'NovaDS_Game.nds'
                    okay = code == 0 and rom.is_file()
                    self.build_running = False
                    self.build_button.configure(state='normal')
                    if okay:
                        self._append_build_output(f'\nSUCCESS: {rom}\n')
                        self._log(f'ROM created: {rom}')
                        messagebox.showinfo('Build successful', f'ROM created at:\n{rom}', parent=self.build_log_window)
                    else:
                        explanation = failure or (f'Build process returned exit code {code}.' if code else
                                                 'Make finished but NovaDS_Game.nds was not produced.')
                        self._append_build_output(f'\nFAILED: {explanation}\n')
                        self._log('Build failed — see Build Output (Copy Log / Save Log).')
                        # Avoid a huge popup hiding the useful compiler details.
                        messagebox.showerror('ROM build failed',
                             explanation + '\n\nThe complete error is in the Build Output window.',
                             parent=self.build_log_window)
                    self._update_title()
        except queue.Empty:
            pass
        if self.build_running:
            self.root.after(85, self._poll_build_events)

    def build(self):
        if self.build_running:
            self.show_build_output()
            return
        self._apply_project_name()
        if self.export_path is None and not self.export():
            return
        self.show_build_output()
        self.build_log_content.clear()
        if self.build_log_text:
            self.build_log_text.configure(state='normal')
            self.build_log_text.delete('1.0', 'end')
            self.build_log_text.configure(state='disabled')
        try:
            export_to(self.export_path, self.project, self.project_path.parent if self.project_path else Path.cwd())
            cmd = self._build_command()
        except (RuntimeError, OSError, ValueError) as exc:
            self._append_build_output(f'Build could not start: {exc}\n')
            messagebox.showerror('Cannot start build', str(exc), parent=self.build_log_window)
            return
        self._append_build_output('NovaDS Studio 1.1.1 — ROM build\n')
        self._append_build_output(f'Project: {self.export_path}\n')
        self._append_build_output(f'Command: {subprocess.list2cmdline(cmd)}\n\n')
        self.build_running = True
        self.build_button.configure(state='disabled')
        self._log('Building ROM — follow the output window...')
        def worker():
            try:
                flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
                # Run source preparation under the SAME Python interpreter that
                # launched NovaDS. devkitPro MSYS2 deliberately has its own PATH
                # and may not contain a `python` command (especially on Windows).
                # Preparing before make also repairs old/incomplete lua/ folders.
                prep = [sys.executable, '-u', 'setup_lua.py']
                self.build_events.put(('text',
                    'Preparing Lua using editor Python: ' + sys.executable + '\n'))
                with subprocess.Popen(prep, cwd=str(self.export_path),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                            errors='replace', bufsize=1, creationflags=flags) as process:
                    for line in process.stdout:
                        self.build_events.put(('text', line))
                    prep_code = process.wait()
                if prep_code != 0:
                    self.build_events.put(('done', (prep_code,
                        'Lua source preparation failed. See the lines above.')))
                    return
                self.build_events.put(('text',
                    'Lua preparation complete. Starting devkitPro build...\n\n'))
                with subprocess.Popen(cmd, cwd=str(self.export_path),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                            errors='replace', bufsize=1, creationflags=flags) as process:
                    for line in process.stdout:
                        self.build_events.put(('text', line))
                    code = process.wait()
                self.build_events.put(('done', (code, '')))
            except Exception as exc:
                self.build_events.put(('done', (-1, str(exc))))
        threading.Thread(target=worker, name='novads-build', daemon=True).start()
        self.root.after(85, self._poll_build_events)

    def _close(self):
        if self._ok_to_discard(): self.root.destroy()


def main():
    root = tk.Tk()
    Editor(root)
    root.mainloop()
