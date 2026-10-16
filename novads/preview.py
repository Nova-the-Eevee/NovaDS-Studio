"""Canvas preview with pixel-rasterized textured meshes. Not a DS emulator."""
import math
import base64
import tkinter as tk
from pathlib import Path
from .compiler import asset_path

_IMAGE_CACHE = {}

W, H = 256, 192
PIXEL_FONT = "TkFixedFont"


def lighten(rgb, factor):
    rgb = rgb.lstrip("#")
    values = [int(rgb[i:i+2], 16) for i in (0, 2, 4)]
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v * factor))) for v in values)


def project_point(point, angle, obj, camera=None):
    """Approximate PC preview camera; DS GPU projection remains authoritative."""
    x,y,z=point
    c,s=math.cos(angle),math.sin(angle)
    x,z=x*c+z*s,z*c-x*s
    c,s=math.cos(angle*.5),math.sin(angle*.5)
    y,z=y*c-z*s,y*s+z*c
    half_size=float(obj['size'])*.5
    x=x*half_size+float(obj['x'])
    y=y*half_size+float(obj['y'])
    z=z*half_size+float(obj['z'])
    cam=camera or {}
    x-=cam.get('x',0);y-=cam.get('y',0);z-=cam.get('z',5)
    yaw=math.radians(cam.get('yaw',0))
    cy,sy=math.cos(yaw),math.sin(yaw)
    x,z=cy*x-sy*z,sy*x+cy*z
    pitch=math.radians(cam.get('pitch',0))
    cp,sp=math.cos(pitch),math.sin(pitch)
    y,z=cp*y+sp*z,-sp*y+cp*z
    depth=max(0.15,-z)
    focal=128/max(.2,math.tan(math.radians(cam.get('fov',65))*.5))
    return (128+focal*x/depth,96-focal*y/depth,depth)


VERTICES = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
            (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
FACES = [([0,1,2,3], .55),([4,5,6,7], 1.0),([0,4,7,3],.68),
         ([1,5,6,2],.78),([3,2,6,7],1.08),([0,1,5,4],.42)]


def draw(canvas, p, selected_id=None, time_seconds=0, scale=1.65, project_base=None):
    """Draw a stacked DS preview; canvas must be sized ~430x690."""
    canvas.delete("all")
    canvas._sprite_images = []
    ox = max(19, (canvas.winfo_width() - int(W*scale))//2)
    ytops = [28, 28 + int(H*scale) + 40]
    w, h = int(W*scale), int(H*scale)
    canvas.create_rectangle(ox-7, 8, ox+w+7, ytops[1]+h+15,
                            fill="#424A56", outline="#85909C", width=2)
    canvas.create_rectangle(ox-3, ytops[0]+h+9, ox+w+3, ytops[1]-8,
                            fill="#2E343D", outline="")
    for screen, y0 in zip(("top", "bottom"), ytops):
        color = p["background_"+screen]
        canvas.create_rectangle(ox, y0, ox+w, y0+h, fill=color, outline="#1B2430", width=2)
        canvas.create_text(ox+6, y0-11, anchor="w", fill="#DBE6F2",
                           text=f"{screen.upper()} 256 × 192", font=("Consolas", 9, "bold"))
        primary=p.get('background_layers',{}).get(screen)
        extras=p.get('extra_background_layers',{}).get(screen,[])
        layers=([primary] if primary else [])+extras
        camera_x=camera_y=0
        target=p.get('camera_follow',{}).get(screen,0)
        if target:
            obj=next((o for o in p['objects'] if o['id']==target),None)
            if obj:
                camera_x=float(obj['x'])-120
                camera_y=float(obj['y'])-88
        # Draw back-to-front: BG3 behind BG2 behind sprites.
        for layer in reversed(layers):
            try:
                from fractions import Fraction
                resolved=asset_path(layer['path'],project_base or Path.cwd())
                scx=round(layer.get('scroll_x',0)+camera_x*layer.get('parallax',1))
                scy=round(layer.get('scroll_y',0)+camera_y*layer.get('parallax',1))
                fraction=Fraction(scale).limit_denominator(6)
                zoom,sub=fraction.numerator,fraction.denominator
                tilemap=layer.get('tiles',[]) if layer.get('tilemap') else []
                tw=layer.get('map_width',32)
                world=tw*8 if tilemap else 256
                sx=scx%world;sy=scy%world
                stamp=hash(tuple(tilemap)) if tilemap else 0
                key=('BGv053',str(resolved),resolved.stat().st_mtime_ns,sx,sy,stamp,zoom,sub)
                if key not in _IMAGE_CACHE:
                    source=tk.PhotoImage(file=str(resolved))
                    area=tk.PhotoImage(width=256,height=192)
                    if tilemap:
                        # Each visible 8x8 cell samples the 128x128 atlas.
                        for dy in range(0,192+8,8):
                            for dx in range(0,256+8,8):
                                world_x=(sx+dx)//8;world_y=(sy+dy)//8
                                oxp=-(sx%8);oyp=-(sy%8)
                                world_x=((sx//8)+(dx//8))%tw
                                world_y=((sy//8)+(dy//8))%tw
                                tile_id=tilemap[world_y*tw+world_x]
                                if tile_id==0:continue
                                ax=(tile_id%16)*8;ay=(tile_id//16)*8
                                dstx=dx+oxp;dsty=dy+oyp
                                cx=max(0,-dstx);cy=max(0,-dsty)
                                cw=min(8,256-dstx)-cx
                                ch=min(8,192-dsty)-cy
                                if cw<=0 or ch<=0:continue
                                area.tk.call(str(area),'copy',str(source),'-from',ax+cx,ay+cy,
                                             ax+cx+cw,ay+cy+ch,'-to',dstx+cx,dsty+cy)
                    else:
                        y=0
                        while y<192:
                            py=(sy+y)%256;ny=min(192-y,256-py)
                            x=0
                            while x<256:
                                px=(sx+x)%256;nx=min(256-x,256-px)
                                area.tk.call(str(area),'copy',str(source),'-from',px,py,px+nx,py+ny,'-to',x,y)
                                x+=nx
                            y+=ny
                    pic=area.zoom(zoom).subsample(sub)
                    if len(_IMAGE_CACHE)>60:_IMAGE_CACHE.clear()
                    _IMAGE_CACHE[key]=pic
                pic=_IMAGE_CACHE[key]
                canvas._sprite_images.append(pic)
                canvas.create_image(ox,y0,image=pic,anchor='nw')
                if layer.get('affine'):
                    canvas.create_text(ox+5,y0+10,anchor='w',fill='#F2F8FE',
                                      text='Affine preview: unrotated',font=('Consolas',7))
            except Exception:
                canvas.create_text(ox+w/2,y0+15,fill='#F48D99',
                                   text='BG / tileset unavailable',font=('Consolas',9))
        if (p["mode"]=="3d2d" and screen=="top") or p["mode"]=="dual3d":
            rects = []
            for obj in p["objects"]:
                if obj.get("scene","Main") != p.get("active_scene","Main") or obj["type"] not in ("Cube3D","Mesh3D") or (p["mode"]=="dual3d" and obj.get("screen","top")!=screen):
                    continue
                angle = (float(obj.get('rot_y',0))+time_seconds*60*float(obj['spin'])) * math.pi/180
                if obj['type']=='Mesh3D':
                    try:
                        from .meshassets import parse_obj,simplify,pack_ds
                        key=obj['mesh'];entry=p['mesh_assets'][key]
                        src=(Path(project_base or Path.cwd())/entry['path']).resolve()
                        cachekey=('objmesh',str(src),src.stat().st_mtime_ns,entry['target_triangles'])
                        if cachekey not in _IMAGE_CACHE:
                            mesh=parse_obj(src)
                            if entry['target_triangles'] and entry['target_triangles']<len(mesh.triangles):
                                mesh=simplify(mesh,entry['target_triangles'])
                            verts,tri=pack_ds(mesh)
                            _IMAGE_CACHE[cachekey]=(verts,tri,mesh)
                        raw_verts,triangles,mesh=_IMAGE_CACHE[cachekey]
                        vertices=[project_point(tuple(v/4096 for v in pt),angle,obj,(p.get('camera_bottom3d') if screen=='bottom' and p['mode']=='dual3d' else p.get('camera_3d'))) for pt in raw_verts]
                        # Rasterize from the same 12.4 UVs / RGB5551 pixels
                        # that the exporter sends to the Nintendo DS GPU.
                        # Formerly only 4 flat-colored subtriangles per edge
                        # were sampled, making patterned faces appear solid.
                        from fractions import Fraction
                        from .meshassets import pack_ds_textured
                        from .texassets import convert_texture
                        from .texture_preview import render_mesh, png_rgba
                        atlas = {}
                        for mat, filename in mesh.textures.items():
                            texfile = Path(filename)
                            if texfile.is_file():
                                atlas[mat] = texfile
                        if entry.get('texture'):
                            texfile = (Path(project_base or Path.cwd()) / entry['texture']).resolve()
                            if texfile.is_file():
                                atlas = {mat:texfile for _,_,_,mat in mesh.triangles}
                        materials = {}
                        texels = {}
                        for mat, texfile in atlas.items():
                            stat = texfile.stat()
                            tkey = ('ds_texture_preview', str(texfile), stat.st_mtime_ns)
                            if tkey not in _IMAGE_CACHE:
                                _IMAGE_CACHE[tkey] = convert_texture(texfile)
                            tex = _IMAGE_CACHE[tkey]
                            tex_id = len(texels)
                            texels[tex_id] = (tex.width,tex.height,tex.pixels)
                            materials[mat] = (tex_id,tex.width,tex.height)
                        _, gpu_faces = pack_ds_textured(mesh,materials)
                        result=render_mesh(vertices,gpu_faces[:900],texels)
                        if result is not None:
                            fraction=Fraction(scale).limit_denominator(6)
                            zoom,sub=fraction.numerator,fraction.denominator
                            # Animated meshes change angle nearly every frame;
                            # don't retain a new Tk image forever in the global
                            # cache. Canvas references keep just the active frame.
                            png=png_rgba(result)
                            picture=tk.PhotoImage(data=base64.b64encode(png).decode('ascii'),format='png')
                            pic=picture.zoom(zoom).subsample(sub)
                            canvas._sprite_images.append(pic)
                            depth=sum(v[2] for v in vertices)/len(vertices)
                            rects.append((depth,('bitmap',pic,result.x,result.y),obj,'',True))
                    except Exception:
                        pass
                    continue
                vertices = [project_point(pt, angle, obj,(p.get('camera_bottom3d') if screen=='bottom' and p['mode']=='dual3d' else p.get('camera_3d'))) for pt in VERTICES]
                for face, shade in FACES:
                    poly = [vertices[i] for i in face]
                    mid_depth = sum(x[2] for x in poly) / 4
                    points = []
                    for x,y,_ in poly:
                        points.extend([ox+x*scale, y0+y*scale])
                    rects.append((mid_depth, points, obj, lighten(obj['color'], shade),False))
            # Painter order across cube faces / cubes.
            rects.sort(key=lambda f:f[0], reverse=True)
            for _, points, obj, face_color, textured in rects:
                tags = ("object", f"object:{obj['id']}")
                if isinstance(points,tuple) and points[0]=='bitmap':
                    _,pic,px,py=points
                    canvas.create_image(ox+px*scale,y0+py*scale,image=pic,anchor='nw',tags=tags)
                    continue
                canvas.create_polygon(points, fill=face_color,
                                      outline=face_color if textured else "#27384A", width=1, tags=tags)
                if obj["id"] == selected_id and not textured:
                    canvas.create_line(points+[points[0],points[1]], fill="#9EFFF0", width=2,
                                       tags=tags)
        for obj in p["objects"]:
            if obj.get("scene","Main") != p.get("active_scene","Main") or obj["type"] != "Sprite2D" or obj["screen"] != screen:
                continue
            x = ox + (int(obj["x"])-camera_x)*scale
            y = y0 + (int(obj["y"])-camera_y)*scale
            tags = ("object", f"object:{obj['id']}")
            try:
                asset_info=p['assets'][obj['asset']]
                asset=asset_info['path']
                resolved=asset_path(asset,project_base or Path.cwd())
                stat=resolved.stat()
                from .pngassets import read_png
                sheet_w=asset_info.get('frame_width')
                sheet_h=asset_info.get('frame_height')
                if sheet_w and sheet_h:
                    full=tk.PhotoImage(file=str(resolved))
                    columns=full.width()//sheet_w
                    frame_count=columns*(full.height()//sheet_h)
                    fnum=int(obj.get('frame',0))%frame_count
                    fps=float(obj.get('fps',0))
                    if fps>0 and obj.get('loop',True):
                        fnum=(fnum+int(time_seconds*fps))%frame_count
                    px=(fnum%columns)*sheet_w;py=(fnum//columns)*sheet_h
                    key=('sprite_frame',str(resolved),stat.st_mtime_ns,fnum)
                    if key not in _IMAGE_CACHE:
                        base=tk.PhotoImage(width=sheet_w,height=sheet_h)
                        base.tk.call(str(base),'copy',str(full),'-from',px,py,px+sheet_w,py+sheet_h,'-to',0,0)
                        if len(_IMAGE_CACHE)>100:_IMAGE_CACHE.clear()
                        _IMAGE_CACHE[key]=base
                    base=_IMAGE_CACHE[key]
                else:
                    key=('sprite_base',str(resolved),stat.st_mtime_ns)
                    if key not in _IMAGE_CACHE:
                        _IMAGE_CACHE[key]=tk.PhotoImage(file=str(resolved))
                    base=_IMAGE_CACHE[key]
                zoom=max(1,round(scale))
                flipx=bool(obj.get('flip_x',False));flipy=bool(obj.get('flip_y',False))
                angle=float(obj.get('angle',0));sx=float(obj.get('scale_x',1));sy=float(obj.get('scale_y',1))
                transkey=(key,zoom,flipx,flipy,angle,sx,sy)
                if transkey not in _IMAGE_CACHE:
                    try:
                        # Pillow is optional; DS ROM never depends on it.
                        from PIL import Image, ImageTk, ImageOps
                        _,_,rgba=read_png(resolved,sprite_sheet=bool(sheet_w))
                        iw=sheet_w or base.width();ih=sheet_h or base.height()
                        if sheet_w:
                            img=Image.frombytes('RGBA',(full.width(),full.height()),rgba)
                            img=img.crop((px,py,px+iw,py+ih))
                        else:
                            img=Image.frombytes('RGBA',(iw,ih),rgba)
                        if flipx:img=ImageOps.mirror(img)
                        if flipy:img=ImageOps.flip(img)
                        img=img.resize((max(1,round(iw*sx*scale)),max(1,round(ih*sy*scale))),Image.Resampling.NEAREST)
                        if angle:img=img.rotate(-angle,Image.Resampling.NEAREST,expand=True)
                        pic=ImageTk.PhotoImage(img,master=canvas)
                    except (ImportError,ValueError,OSError):
                        pic=base.zoom(zoom)
                    if len(_IMAGE_CACHE)>100:_IMAGE_CACHE.clear()
                    _IMAGE_CACHE[transkey]=pic
                pic=_IMAGE_CACHE[transkey]
                canvas._sprite_images.append(pic)
                canvas.create_image(x,y,image=pic,anchor='nw',tags=tags)
                width,height=pic.width(),pic.height()
            except Exception:
                width, height = 16*scale, 16*scale
                canvas.create_rectangle(x,y,x+width,y+height,fill='#F15D75',tags=tags)
                canvas.create_text(x+width/2,y+height/2,fill='white',text='?',tags=tags)
            if obj.get('collider',False) and obj['id']==selected_id:
                try:
                    natural_w=int(obj.get('collider_width',0)) or (asset_info.get('frame_width') or base.width())
                    natural_h=int(obj.get('collider_height',0)) or (asset_info.get('frame_height') or base.height())
                except (NameError,TypeError):natural_w,natural_h=16,16
                canvas.create_rectangle(x,y,x+natural_w*scale,y+natural_h*scale,
                    outline='#FFB469' if obj.get('trigger') else '#7EE9AC',width=2,dash=(4,2),tags=tags)
            if obj['id'] == selected_id:
                canvas.create_rectangle(x-3,y-3,x+width+3,y+height+3,
                    outline='#9EFFF0',dash=(3,2),width=2,tags=tags)
        if screen == "bottom" and not layers:
            canvas.create_text(ox+6,y0+h-7,anchor="sw",fill="#B8DBEE",
                               text="Scripts execute in ROM\nPreview only", font=("Consolas", 9))
    canvas.create_text(ox+w/2, ytops[1]+h+33, fill="#BBCAD9",
                       text="NovaDS Studio 1.0  •  Lua/UI run in ROM", font=("Consolas", 9))
    return ox, ytops, scale
