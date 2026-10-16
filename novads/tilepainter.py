"""Tkinter 8x8 tilemap painter; no Pillow or external GUI modules required."""
from collections import deque
from pathlib import Path
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .model import clean_project
from .compiler import asset_path
from .pngassets import read_png

ZOOM=2
TILE=8*ZOOM

class TilePainter:
    def __init__(self,editor,screen,slot=0):
        self.editor=editor;self.screen=screen;self.slot=slot
        old=editor.project.get('background_layers',{}).get(screen) if slot==0 else (editor.project.get('extra_background_layers',{}).get(screen) or [None])[0]
        if old and not old.get('tilemap'):
            raise ValueError('This slot contains an imported PNG background. Remove it or choose an empty slot first.')
        self.layer=dict(old) if old else {'name':f'layer{slot}','tilemap':True,'path':'',
             'map_width':32,'map_height':32,'tiles':[0]*1024,'affine':False,
             'scroll_x':0,'scroll_y':0,'angle':0,'scale':1,'parallax':1}
        self.tiles=self.layer['tiles'][:]
        self.width=self.layer['map_width'];self.height=self.layer['map_height']
        self.current=1;self.tool=tk.StringVar(value='pencil');self.tilepics=[]
        self.win=tk.Toplevel(editor.root)
        self.win.title(f'NovaDS Tile Painter — {screen.upper()} BG{2+slot}')
        sw,sh=editor.root.winfo_screenwidth(),editor.root.winfo_screenheight()
        self.win.geometry(f'{min(1010,sw-40)}x{min(750,sh-100)}')
        self.win.minsize(490,360)
        self.win.transient(editor.root)
        self._layout()
        if self.layer.get('path'):
            try:self.load_atlas(asset_path(self.layer['path'],editor.project_path.parent))
            except Exception:pass
        self.redraw()

    def _layout(self):
        top=ttk.Frame(self.win,padding=8);top.pack(fill='x')
        ttk.Label(top,text='Tilemap:').pack(side='left')
        self.map_size=tk.StringVar(value=str(self.width))
        box=ttk.Combobox(top,values=['32','64'],state='readonly',width=4,textvariable=self.map_size)
        box.pack(side='left',padx=5);box.bind('<<ComboboxSelected>>',self.resize)
        for title,value in [('Pencil','pencil'),('Eraser','erase'),('Flood Fill','fill')]:
            ttk.Radiobutton(top,text=title,variable=self.tool,value=value).pack(side='left',padx=4)
        ttk.Button(top,text='Import 128×128 Tileset...',command=self.import_atlas).pack(side='left',padx=7)
        ttk.Button(top,text='Save Map',command=self.save).pack(side='right',padx=3)
        body=ttk.Panedwindow(self.win,orient='horizontal');body.pack(fill='both',expand=True,padx=8,pady=6)
        palette=ttk.Frame(body);body.add(palette,weight=1)
        ttk.Label(palette,text='TILESET (click tile)').pack(anchor='w')
        self.pal=tk.Canvas(palette,width=16*TILE,height=16*TILE,background='#394b5a',highlightthickness=0)
        self.pal.pack(fill='both',expand=False)
        self.pal.bind('<Button-1>',self.select_tile)
        self.tilelabel=ttk.Label(palette,text='Tile 1');self.tilelabel.pack(pady=6)
        ttk.Label(palette,text='Tile 0 = empty\nRight-click to erase.\nCtrl+wheel not needed: scrollbars below.',wraplength=270).pack(anchor='w')
        canvas_holder=ttk.Frame(body);body.add(canvas_holder,weight=3)
        ttk.Label(canvas_holder,text='MAP (drag to paint)').pack(anchor='w')
        grid_holder=ttk.Frame(canvas_holder);grid_holder.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(grid_holder,background='#22384e',highlightthickness=0)
        vx=ttk.Scrollbar(grid_holder,orient='horizontal',command=self.canvas.xview)
        vy=ttk.Scrollbar(grid_holder,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=vx.set,yscrollcommand=vy.set)
        self.canvas.grid(row=0,column=0,sticky='nsew');vy.grid(row=0,column=1,sticky='ns');vx.grid(row=1,column=0,sticky='ew')
        grid_holder.columnconfigure(0,weight=1);grid_holder.rowconfigure(0,weight=1)
        self.canvas.bind('<Button-1>',self.paint)
        self.canvas.bind('<B1-Motion>',self.paint)
        self.canvas.bind('<Button-3>',self.erase)
        self.canvas.bind('<B3-Motion>',self.erase)
        self.canvas.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-1 if e.delta>0 else 1,'units'))
        footer=ttk.Frame(self.win,padding=6);footer.pack(fill='x')
        ttk.Label(footer,text='Name:').pack(side='left')
        self.name=tk.StringVar(value=self.layer['name']);ttk.Entry(footer,width=14,textvariable=self.name).pack(side='left',padx=4)
        ttk.Label(footer,text='Solid tile IDs:').pack(side='left',padx=(8,2))
        self.solid_ids=tk.StringVar(value=','.join(str(v) for v in self.layer.get('solid_tile_ids',[])))
        ttk.Entry(footer,width=14,textvariable=self.solid_ids).pack(side='left',padx=2)
        ttk.Label(footer,text='Parallax:').pack(side='left')
        self.parallax=tk.StringVar(value=str(self.layer.get('parallax',1)))
        ttk.Entry(footer,width=6,textvariable=self.parallax).pack(side='left',padx=3)
        ttk.Button(footer,text='Cancel',command=self.win.destroy).pack(side='right')
        self.win.protocol('WM_DELETE_WINDOW',self.win.destroy)

    def load_atlas(self,path):
        w,h,_=read_png(path,background=True)
        if (w,h)!=(128,128):raise ValueError('Tilemap tileset must be a 128×128 PNG')
        atlas=tk.PhotoImage(file=str(path))
        pics=[]
        for tile in range(256):
            small=tk.PhotoImage(width=8,height=8)
            x=(tile%16)*8;y=(tile//16)*8
            small.tk.call(str(small),'copy',str(atlas),'-from',x,y,x+8,y+8,'-to',0,0)
            pics.append(small.zoom(ZOOM,ZOOM))
        self.tilepics=pics
        self.pal.delete('all')
        for i,img in enumerate(pics):self.pal.create_image((i%16)*TILE,(i//16)*TILE,image=img,anchor='nw')
        self.draw_selection()

    def import_atlas(self):
        if self.editor.project_path is None and not self.editor.save_as():return
        path=filedialog.askopenfilename(parent=self.win,filetypes=[('PNG images','*.png')])
        if not path:return
        try:
            w,h,_=read_png(path,background=True)
            if (w,h)!=(128,128):raise ValueError('Expected a 128x128 PNG atlas of 16x16 tiles')
            target=self.editor.project_path.parent/'assets'/f'tiles_{self.screen}_{self.slot}.png'
            target.parent.mkdir(exist_ok=True,parents=True)
            if Path(path).resolve()!=target.resolve():shutil.copyfile(path,target)
            self.layer['path']=f'assets/{target.name}'
            self.load_atlas(target);self.redraw()
        except (ValueError,OSError) as exc:messagebox.showerror('PNG import',str(exc),parent=self.win)

    def select_tile(self,event):
        tx=event.x//TILE;ty=event.y//TILE
        if 0<=tx<16 and 0<=ty<16:
            self.current=ty*16+tx;self.tilelabel.config(text=f'Tile {self.current}')
            self.draw_selection()

    def draw_selection(self):
        self.pal.delete('selector')
        x=self.current%16*TILE;y=self.current//16*TILE
        self.pal.create_rectangle(x,y,x+TILE-1,y+TILE-1,outline='#ffda57',width=2,tags='selector')

    def resize(self,_=None):
        new=int(self.map_size.get())
        if new==self.width:return
        vals=[0]*(new*new)
        for y in range(min(new,self.height)):
            for x in range(min(new,self.width)):vals[y*new+x]=self.tiles[y*self.width+x]
        self.tiles=vals;self.width=self.height=new;self.redraw()

    def coords(self,event):
        x=int(self.canvas.canvasx(event.x))//TILE
        y=int(self.canvas.canvasy(event.y))//TILE
        return (x,y) if 0<=x<self.width and 0<=y<self.height else (None,None)

    def _set(self,x,y,value):
        if self.tiles[y*self.width+x]==value:return
        self.tiles[y*self.width+x]=value
        self.draw_one(x,y)

    def erase(self,event):
        x,y=self.coords(event)
        if x is not None:self._set(x,y,0)

    def paint(self,event):
        x,y=self.coords(event)
        if x is None:return
        if self.tool.get()=='fill':
            old=self.tiles[y*self.width+x];new=self.current
            if old==new:return
            pending=deque([(x,y)]);seen=set()
            while pending:
                px,py=pending.popleft()
                if (px,py) in seen or not(0<=px<self.width and 0<=py<self.height):continue
                seen.add((px,py))
                if self.tiles[py*self.width+px]!=old:continue
                self._set(px,py,new)
                pending.extend(((px-1,py),(px+1,py),(px,py-1),(px,py+1)))
        else:self._set(x,y,0 if self.tool.get()=='erase' else self.current)

    def draw_one(self,x,y):
        tag=f'cell_{x}_{y}'
        self.canvas.delete(tag)
        if self.tiles[y*self.width+x] and self.tilepics:
            self.canvas.create_image(x*TILE,y*TILE,anchor='nw',image=self.tilepics[self.tiles[y*self.width+x]],tags=tag)
        else:
            self.canvas.create_rectangle(x*TILE,y*TILE,(x+1)*TILE,(y+1)*TILE,
                fill=('#293947' if (x+y)%2 else '#324554'),outline='',tags=tag)
        self.canvas.create_rectangle(x*TILE,y*TILE,(x+1)*TILE,(y+1)*TILE,
           outline='#526879',width=1,tags=tag)

    def redraw(self):
        self.canvas.delete('all')
        self.canvas.configure(scrollregion=(0,0,self.width*TILE,self.height*TILE))
        for y in range(self.height):
            for x in range(self.width):self.draw_one(x,y)

    def save(self):
        try:
            if not self.layer.get('path'):raise ValueError('Import a 128×128 tileset PNG first')
            old=self.editor.project
            candidate=__import__('copy').deepcopy(old)
            ids=[int(v.strip()) for v in self.solid_ids.get().split(',') if v.strip()]
            if any(i<0 or i>255 for i in ids):raise ValueError('Solid tile IDs must be 0..255')
            self.layer['solid_tile_ids']=ids
            self.layer.update(name=self.name.get(),tiles=self.tiles[:],map_width=self.width,map_height=self.height,
                              affine=False,tilemap=True,parallax=float(self.parallax.get()))
            if self.slot==0:candidate.setdefault('background_layers',{})[self.screen]=self.layer
            else:candidate.setdefault('extra_background_layers',{}).setdefault(self.screen,[])[:]=[self.layer]
            self.editor.project=clean_project(candidate)
            self.editor._note_changed();self.win.destroy()
        except (ValueError,TypeError) as exc:messagebox.showerror('Invalid tilemap',str(exc),parent=self.win)
