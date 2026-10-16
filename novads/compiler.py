"""NovaDS v0.4 JSON scene -> assets, object tables and embedded real Lua scripts.
The runtime source is identical for all exported games.
"""
from pathlib import Path
from shutil import copyfile
from .model import clean_project, color_rgb
from .pngassets import convert_png, convert_sprite_sheet
from .bgassets import convert_background,convert_tilemap
from .scripting import validate_script
from .wavassets import convert_wav,MAX_TOTAL_BYTES
from .meshassets import parse_obj,simplify,pack_ds,pack_ds_textured,simplify_lod,MAX_EXPORT_FACES
from .texassets import convert_texture,MAX_TEXTURE_BYTES
import json
import re

ROOT=Path(__file__).resolve().parent.parent
TEMPLATES=ROOT/'templates'


def rgb5(s): return tuple(v>>3 for v in color_rgb(s))
def fixed12(n): return round(float(n)*4096)
def slug(name):
    return re.sub(r'[^A-Za-z0-9_-]','_',name).strip('_- ')[:38] or 'project'


def asset_path(relative_path, base):
    if relative_path==':builtin/nova.png':
        return ROOT/'novads'/'assets'/'nova.png'
    base=Path(base).resolve()
    path=(base / relative_path).resolve()
    if not path.is_relative_to(base): raise ValueError('Asset path escapes project directory')
    if not path.is_file(): raise FileNotFoundError(f'Sprite PNG not found: {path}')
    return path


def asset_conversion(project, project_base):
    """Return images in project asset insertion order; fail visibly on invalid PNGs."""
    p=clean_project(project)
    result={}
    for key,asset in p['assets'].items():
        path=asset_path(asset['path'],project_base)
        if 'frame_width' in asset:
            result[key]=convert_sprite_sheet(path,asset['frame_width'],asset['frame_height'])
        else:
            result[key]=(convert_png(path),)
    return result


def mesh_conversion(project, base):
    """Export geometry with shared material texture indices and an explicit VRAM budget."""
    p=clean_project(project)
    out={};textures={};base=Path(base).resolve()
    for key,entry in p['mesh_assets'].items():
        source=(base/entry['path']).resolve()
        if not source.is_relative_to(base) or not source.is_file():
            raise FileNotFoundError(f'OBJ mesh missing: {source}')
        model=parse_obj(source)
        target=entry['target_triangles'] or MAX_EXPORT_FACES
        if len(model.triangles)>target:model=simplify(model,target)
        if len(model.triangles)>MAX_EXPORT_FACES:
            raise ValueError(f'{key}: {len(model.triangles)} triangles exceed max {MAX_EXPORT_FACES}; simplify more')
        per_material={}
        override=entry.get('texture','')
        if override:
            texpath=asset_path(override,base)
            model.textures={mat:str(texpath) for mat in {face[3] for face in model.triangles}}
        for mat,filename in model.textures.items():
            path=Path(filename).resolve()
            # A texture must be part of the portable OBJ/MTL directory bundle.
            allowed=(path.is_relative_to(source.parent.resolve()) or (override and path==texpath.resolve()))
            if not allowed or not path.is_file():
                raise FileNotFoundError(f'{key}: referenced PNG texture missing or outside model folder: {path}')
            if path not in textures:
                textures[path]=convert_texture(path)
            t=textures[path]
            per_material[mat]=(list(textures).index(path),t.width,t.height)
        out[key]={'mesh':model,'packed':pack_ds_textured(model,per_material)}
        lodtarget=entry.get('lod_triangles',0)
        if lodtarget and len(model.triangles)>lodtarget:
            lod=simplify_lod(model,lodtarget)
            out[key+'__LOD']={'mesh':lod,'packed':pack_ds_textured(lod,per_material),'lod_of':key}
    if sum(t.width*t.height*2 for t in textures.values())>MAX_TEXTURE_BYTES:
        raise ValueError('3D textures exceed 128 KiB bank A. Shrink PNG textures (or use fewer materials).')
    for scene in p['scenes']:
        total=sum(12 if obj['type']=='Cube3D' else
                  max(len(out[key]['packed'][1]) for key in ([obj['mesh']] + (obj.get('animation3d') or {}).get('mesh_frames',[]))) if obj['type']=='Mesh3D' else 0
                  for obj in p['objects'] if obj['scene']==scene)
        if total>1900:raise ValueError(f'{scene}: {total} 3D polygons exceed 1900 scene budget (DS limit ~2048)')
    return out,textures


def get_layers(project):
    """Flatten scene layers into stable hardware slots: top0/top1/bottom0/bottom1."""
    p=clean_project(project)
    result={}
    for screen in ('top','bottom'):
        layer=p['background_layers'].get(screen)
        if layer:result[f'{screen}0']=layer
        for i,extra in enumerate(p.get('extra_background_layers',{}).get(screen,[]),start=1):
            result[f'{screen}{i}']=extra
    return result


def background_conversion(project, base):
    return {key:(convert_tilemap(asset_path(layer['path'],base),layer) if layer.get('tilemap')
                 else convert_background(asset_path(layer['path'],base),affine=layer['affine']))
            for key,layer in get_layers(project).items()}

def _words(tiles):
    assert len(tiles)%2==0
    return [tiles[i] | (tiles[i+1]<<8) for i in range(0,len(tiles),2)]


def _array_words(words):
    return '\n'.join('    '+', '.join('0x%04X'%x for x in words[i:i+12])+',' for i in range(0,len(words),12))


def script_path(relative_path, base):
    base=Path(base).resolve()
    path=(base / relative_path).resolve()
    if not path.is_relative_to(base):raise ValueError('Script path escapes project directory')
    if not path.is_file():raise FileNotFoundError(f'Script not found: {path}')
    return path


def script_conversion(project, project_base):
    p=clean_project(project)
    compiled={}
    for obj in p['objects']:
        relative=obj['script']
        if relative and relative not in compiled:
            text=script_path(relative,project_base).read_text(encoding='utf-8')
            try:validate_script(text)
            except ValueError as exc:raise ValueError(f'{relative}: {exc}') from exc
            compiled[relative]=text
    return compiled


def _hardware_map(entries, width, height):
    """2D BG map quadrants: 512x512 is four consecutive 32x32 maps."""
    if (width,height)==(32,32):return tuple(entries)
    if (width,height)!=(64,64):raise ValueError('Expected square 32x32 or 64x64 tilemap')
    return tuple(entries[(block_y*32+y)*64 + (block_x*32+x)]
            for block_y in range(2) for block_x in range(2)
            for y in range(32) for x in range(32))


def scale_rgb555(value, brightness):
    """PC-side material tint: no per-face color math required on the ARM9."""
    channels=[min(31,max(0,round(((value>>shift)&31)*brightness))) for shift in (0,5,10)]
    return channels[0]|(channels[1]<<5)|(channels[2]<<10)


def scene_source(project, conversions, programs=None, backgrounds=None, sounds=None, meshes=None, textures=None):
    """Render scene metadata as immutable C tables, NOT game-specific logic."""
    p=clean_project(project)
    meshes=meshes or {}
    textures=textures or {}
    keys=list(conversions)
    frame_start={}
    frame_images=[]
    for key in keys:
        frame_start[key]=len(frame_images)
        frame_images.extend(conversions[key])
    if len(frame_images)>256:
        raise ValueError('Maximum 256 total sprite frames in the scene')
    programs=programs or {}
    backgrounds=backgrounds or {}
    script_keys=list(programs)
    sounds=sounds or {}
    lines=['/* Auto-generated scene tables by NovaDS Studio v0.9.4. */',
           '#include "novads_runtime.h"', '#include "scene.h"', '']
    for idx,im in enumerate(frame_images):
        lines += [f'/* Sprite image frame {idx} ({im.width}x{im.height}) */',
                  f'static const u16 nd_tiles_{idx}[] = {{',_array_words(_words(im.tiles)),'};',
                  f'static const u16 nd_palette_{idx}[16] = {{',_array_words(im.palette),'};', '']
    lines.append('static const NdImage images[] = {')
    for idx,im in enumerate(frame_images):
        lines.append(f'    {{ {im.width}, {im.height}, nd_tiles_{idx}, {len(im.tiles)//2}, nd_palette_{idx} }},')
    if not keys: lines.append('    {0,0,0,0,0}, /* empty placeholder */')
    lines.append('};')
    layer_defs=get_layers(p)
    for key,bg in backgrounds.items():
        lines.extend([f'/* BG {key}: {bg.unique_tiles} tiles, {bg.map_width}x{bg.map_height} map */',
                      f'static const u16 bg_tiles_{key}[] = {{',_array_words(_words(bg.tiles)),'};',
                      f'static const u16 bg_map_{key}[{len(bg.tilemap)}] = {{',
                      _array_words(_hardware_map(bg.tilemap,bg.map_width,bg.map_height)), '};',
                      f'static const u16 bg_palette_{key}[16] = {{',_array_words(bg.palette),'};', ''])
    lines.append('static const NdBackground scene_backgrounds[4] = {')
    for screen in ('top','bottom'):
        for slot in range(2):
            key=f'{screen}{slot}'
            if key in backgrounds:
                layer=layer_defs[key];bg=backgrounds[key]
                lines.append('    { bg_tiles_%s, %d, bg_map_%s, %d, bg_palette_%s, %d, %d, %d, %d, %d, %d, %d, %d, %s },' % (
                    key,len(bg.tiles)//2,key,len(bg.tilemap),key,int(layer['affine']),
                    round(layer['scroll_x']),round(layer['scroll_y']),
                    round(layer['angle']*512/360),round(256/layer['scale']),
                    bg.map_width,bg.map_height,round(layer['parallax']*256),
                    json.dumps(layer['name'])))
            else:lines.append('    {0},')
    lines.append('};')
    # Tile collision flags are bit-packed in world-coordinate row-major order.
    # Hardware BG screen-block order is NOT used for collision lookups.
    for key,layer in layer_defs.items():
        solid=set(layer.get('solid_tile_ids',[]))
        if solid:
            width=layer['map_width'];height=layer['map_height']
            bits=[0]*((width*height+7)//8)
            for i,tile_id in enumerate(layer['tiles']):
                if tile_id in solid: bits[i>>3]|=1<<(i&7)
            lines.append(f'static const unsigned char nd_collision_{key}[] = {{')
            lines.extend('    '+', '.join(str(v) for v in bits[i:i+32])+',' for i in range(0,len(bits),32))
            lines.append('};')
    lines.append('static const NdTileCollision scene_tile_collisions[4] = {')
    for screen in ('top','bottom'):
        for slot in range(2):
            key=f'{screen}{slot}'
            if key in layer_defs and layer_defs[key].get('solid_tile_ids'):
                lay=layer_defs[key]
                lines.append('    { nd_collision_%s, %d, %d },' % (key,lay['map_width'],lay['map_height']))
            else:lines.append('    {0},')
    lines.append('};')
    for i,key in enumerate(script_keys):
        # Raw UTF-8 Lua text is in read-only ROM data; loaded once per instance.
        b=programs[key].encode('utf-8')
        lines.append(f'/* Lua: {key} (UTF-8 source, {len(b)} bytes) */')
        lines.append(f'static const unsigned char lua_script_{i}[] = {{')
        for start in range(0,len(b),20):
            lines.append('    '+', '.join(str(v) for v in b[start:start+20])+',')
        if not b:lines.append('    0, /* empty script */')
        lines.append('};')
    lines.append('static const NdScript scene_scripts[] = {')
    for i,key in enumerate(script_keys):
        name=json.dumps('@'+key,ensure_ascii=True)
        lines.append(f'    {{ lua_script_{i}, {len(programs[key].encode("utf-8"))}, {name} }},')
    if not script_keys:lines.append('    {0},')
    lines.append('};')
    # 16-bit direct-color textures live in read-only ROM until uploaded once to VRAM A.
    for i,(path,t) in enumerate(textures.items()):
        lines += [f'/* 3D texture {i}: {path.name} ({t.width}x{t.height}) */',
                  f'static const u16 nd_texture_{i}[] __attribute__((aligned(4))) = {{',
                  _array_words(t.pixels),'};']
    lines.append('static const NdTexture nd_textures[] = {')
    for i,t in enumerate(textures.values()):
        lines.append(f'    {{ nd_texture_{i}, {t.width}, {t.height} }},')
    if not textures:lines.append('    {0},')
    lines.append('};')
    # Geometry arrays are all ROM-resident and shared between object instances.
    for i,(key,info) in enumerate(meshes.items()):
        vertices,faces=info['packed']
        lines.append(f'/* {key}: {len(vertices)} verts, {len(faces)} tris */')
        lines.append(f'static const NdMeshVertex nd_verts_{i}[] = {{')
        lines.extend('    {'+', '.join(map(str,v))+'},' for v in vertices)
        lines.append('};')
        lines.append(f'static const NdMeshFace nd_faces_{i}[] = {{')
        for f in faces:
            tinted=list(f)
            tinted[3]=scale_rgb555(tinted[3],p['camera_3d']['brightness'])
            lines.append('    {'+', '.join(map(str,tinted))+'},')
        lines.append('};')
    lines.append('static const NdMesh nd_meshes[] = {')
    for i,info in enumerate(meshes.values()):
        vertices,faces=info['packed']
        radius12=round(max((sum(q*q for q in v)**0.5 for v in vertices),default=4096))
        lines.append(f'    {{ nd_verts_{i}, nd_faces_{i}, {len(vertices)}, {len(faces)}, {radius12} }},')
    if not meshes:lines.append('    {0},')
    lines.append('};')
    animation_objects=[o for o in p['objects'] if o['type'] in ('Mesh3D','Cube3D') and o.get('animation3d')]
    for i,obj in enumerate(animation_objects):
        clip=obj['animation3d']
        if clip['keys']:
            lines.append(f'static const NdAnimKey3D nd_anim_keys_{i}[] = {{')
            for k in clip['keys']:
                row=[k['frame'],fixed12(k['x'])*16,fixed12(k['y'])*16,fixed12(k['z'])*16,
                     round(k['yaw']*65536/360),round(k['scale']*256)]
                lines.append('    {'+', '.join(map(str,row))+'},')
            lines.append('};')
        if clip['mesh_frames']:
            lines.append(f'static const u16 nd_anim_mesh_{i}[] = {{'+
                         ', '.join(str(list(meshes).index(key)) for key in clip['mesh_frames'])+'};')
    lines.append('static const NdAnim3D nd_animations3d[] = {')
    for i,obj in enumerate(animation_objects):
        clip=obj['animation3d']
        lines.append('    { %s, %s, %d, %s, %d, %d, %d, %d, %d },' % (
            json.dumps(clip['name']),f'nd_anim_keys_{i}' if clip['keys'] else 'NULL',len(clip['keys']),
            f'nd_anim_mesh_{i}' if clip['mesh_frames'] else 'NULL',len(clip['mesh_frames']),
            clip['duration'],round(clip['fps']*256),int(clip['loop']),int(clip['autoplay'])))
    if not animation_objects:lines.append('    {0},')
    lines.append('};')
    anim_index={obj['id']:i for i,obj in enumerate(animation_objects)}
    lines.append('static const NdObjectDef scene_objects[] = {')
    for obj in p['objects']:
        if obj['type'] in ('Cube3D','Mesh3D'):
            r,g,b=rgb5(obj['color'])
            vals=[obj['id'],3 if obj['type']=='Mesh3D' else 1,1 if obj['screen']=='bottom' else 0,fixed12(obj['x']),fixed12(obj['y']),fixed12(obj['z']),
                  fixed12(obj['size']/2),round(obj['spin']*32768/180),0,0,-1,r,g,b,script_keys.index(obj['script']) if obj['script'] else -1]
        else:
            vals=[obj['id'],2,1 if obj['screen']=='bottom' else 0, obj['x'],obj['y'],0,0,0,
                  obj['speed'],1 if obj['controllable'] else 0,frame_start[obj['asset']],0,0,0,
                  script_keys.index(obj['script']) if obj['script'] else -1]
        if obj['type']=='Sprite2D':
            frame_count=len(conversions[obj['asset']])
            if obj['frame']>=frame_count:
                raise ValueError(f'{obj["name"]}: frame {obj["frame"]} exceeds {frame_count} frame(s)')
            vals.extend([frame_count,round(obj['fps']*256),int(obj['loop']),int(obj['flip_x']),int(obj['flip_y']),
                         round(obj['angle']*65536/360),round(obj['scale_x']*256),round(obj['scale_y']*256),obj['frame']])
        else:
            vals.extend([0,0,0,0,0,0,256,256,0])
        if obj['type']=='Sprite2D':
            vals.extend([int(obj['collider']),int(obj['solid']),int(obj['trigger']),int(obj['physics']),
                obj['collider_width'],obj['collider_height'],
                round(obj['velocity_x']*65536),round(obj['velocity_y']*65536),
                round(obj['gravity']*65536),round(obj['friction']*65536),
                obj['collision_layer'],obj['collision_mask']])
        else:vals.extend([0]*12)
        vals.append(p['scenes'].index(obj['scene']))
        vals.extend([list(meshes).index(obj['mesh']) if obj['type']=='Mesh3D' else -1,
                     round(obj.get('rot_x',0)*65536/360) if obj['type']=='Mesh3D' else 0,
                     round(obj.get('rot_y',0)*65536/360) if obj['type']=='Mesh3D' else 0,
                     round(obj.get('rot_z',0)*65536/360) if obj['type']=='Mesh3D' else 0])
        if obj['type'] in ('Cube3D','Mesh3D'):
            vals.extend([int(obj[k]) for k in ('collider3d','solid3d','trigger3d','physics3d','sphere3d')])
            vals.extend([round(obj[k]*65536) for k in ('half_x3d','half_y3d','half_z3d',
                             'velocity_x3d','velocity_y3d','velocity_z3d','gravity3d','friction3d')])
            vals.extend([obj['collision_layer3d'],obj['collision_mask3d']])
        else: vals.extend([0]*15)
        vals.append(anim_index.get(obj['id'],-1))
        if obj['type'] in ('Cube3D','Mesh3D'):
            key=obj.get('mesh','')
            lod_key=key+'__LOD'
            lod_index=list(meshes).index(lod_key) if lod_key in meshes else -1
            vals.extend([int(obj.get('cull3d',True)),lod_index,round(obj.get('lod_distance',8.0)*65536)])
        else: vals.extend([0,-1,0])
        lines.append('    { '+', '.join(str(v) for v in vals)+' },')
    if not p['objects']: lines.append('    {0}, /* empty placeholder */')
    lines.append('};')
    tr,tg,tb=rgb5(p['background_top']); br,bg,bb=rgb5(p['background_bottom'])
    lines.append('static const char *const nd_scene_names[] = {'+', '.join(json.dumps(s) for s in p['scenes'])+'};')
    for i,(key,(data,frames,rate)) in enumerate(sounds.items()):
        lines.append('static const signed char nd_sound_%d[] __attribute__((aligned(4))) = {' % i)
        lines.extend('    '+', '.join(str(b if b<128 else b-256) for b in data[start:start+32])+',' for start in range(0,len(data),32))
        if not data:lines.append('    0,')
        lines.append('};')
    lines.append('static const NdSound nd_sounds[] = {')
    for i,(key,(data,frames,rate)) in enumerate(sounds.items()):
        lines.append('    { %s, nd_sound_%d, %d, %d },' % (json.dumps(key),i,frames,rate))
    if not sounds:lines.append('    {0},')
    lines.append('};')
    lines.extend([f'const NdScene nd_scene = {{',
                  f'    {1 if p["mode"] in ("3d2d","dual3d") else 0},',
                  f'    RGB15({tr},{tg},{tb}), RGB15({br},{bg},{bb}),',
                  f'    {len(p["objects"])}, scene_objects,',
                  f'    {len(frame_images)}, images,',
                  f'    {len(script_keys)}, scene_scripts,',
                  '    scene_backgrounds,',
                  f'    {p.get("camera_follow",{}).get("top",0)}, {p.get("camera_follow",{}).get("bottom",0)},',
                  '    scene_tile_collisions,',
                  '    %d, %d, nd_scene_names,' % (len(p['scenes']),p['scenes'].index(p['active_scene'])),
                  '    %d, nd_sounds,' % len(sounds),
                  '    %d, nd_meshes,' % len(meshes),
                  '    %d, nd_textures,' % len(textures),
                  '    %d, %d, %d, %d, %d, %d,' % (
                      fixed12(p['camera_3d']['x']),fixed12(p['camera_3d']['y']),fixed12(p['camera_3d']['z']),
                      round(p['camera_3d']['yaw']*65536/360),round(p['camera_3d']['pitch']*65536/360),
                      round(p['camera_3d']['fov'])),
                  f'    {len(animation_objects)}, nd_animations3d,',
                  f'    {int(p["camera_3d"]["frustum_culling"])}, {int(p["camera_3d"]["fog_enabled"])},',
                  f'    RGB15({rgb5(p["camera_3d"]["fog_color"])[0]}, {rgb5(p["camera_3d"]["fog_color"])[1]}, {rgb5(p["camera_3d"]["fog_color"])[2]}),',
                  f'    {round(p["camera_3d"]["fog_strength"]*127)}, {round(p["camera_3d"]["brightness"]*256)}, {int(p["camera_3d"]["profiler"])},',
                  '    %d, %d, %d, %d, %d, %d, %d' % (int(p['mode']=='dual3d'),
                     fixed12(p['camera_bottom3d']['x']),fixed12(p['camera_bottom3d']['y']),fixed12(p['camera_bottom3d']['z']),
                     round(p['camera_bottom3d']['yaw']*65536/360),round(p['camera_bottom3d']['pitch']*65536/360),
                     round(p['camera_bottom3d']['fov'])),
                  '};',''])
    return '\n'.join(lines)


def export_to(folder,project,project_base=None):
    p=clean_project(project)
    base=Path(project_base or Path.cwd())
    images=asset_conversion(p,base)
    programs=script_conversion(p,base)
    backgrounds=background_conversion(p,base)
    meshes,textures=mesh_conversion(p,base)
    sounds={}
    for key,entry in p['sounds'].items():
        src=base.joinpath(entry['path']).resolve()
        if not src.is_relative_to(base.resolve()) or not src.is_file():
            raise FileNotFoundError(f'WAV sound asset missing: {src}')
        sounds[key]=convert_wav(src)
    if sum(len(pcm) for pcm,_,_ in sounds.values())>MAX_TOTAL_BYTES:
        raise ValueError('Total PCM sound assets exceed 128 KiB RAM budget')
    # OBJ VRAM: each of the two 2D engines has a 128 KiB sprite bank.
    # The 1D_128 mapping rounds each sprite graphic to a 128-byte boundary.
    for screen in ('top','bottom'):
        used={o['asset'] for o in p['objects'] if o['type']=='Sprite2D' and o['screen']==screen}
        bytes_needed=sum(sum(((im.width*im.height//2+127)//128)*128 for im in images[key])
                         for key in used)
        if bytes_needed>128*1024:
            raise ValueError(f'{screen} sprite graphics need {bytes_needed} bytes; DS OBJ VRAM has 131072')
        affine_count=sum(o['type']=='Sprite2D' and o['screen']==screen and
                         (o['angle']!=0 or o['scale_x']!=1 or o['scale_y']!=1)
                         for o in p['objects'])
        if affine_count>32:
            raise ValueError(f'{screen}: only 32 distinct hardware affine sprite matrices')
    dest=Path(folder)
    dest.mkdir(parents=True,exist_ok=True)
    src=dest/'source'
    src.mkdir(exist_ok=True)
    for filename in ('main.c','novads_runtime.h','scene.h','nd_physics.h','nd_physics.c','nd_physics3d.h','nd_physics3d.c'):
        copyfile(TEMPLATES/filename,src/filename)
    copyfile(TEMPLATES/'Makefile',dest/'Makefile')
    from .banner import write_icon_bmp, make_banner_makefile
    info=p['metadata']
    has_icon=bool(info['icon'])
    if has_icon:
        write_icon_bmp(asset_path(info['icon'],base),dest/'icon.bmp')
    make_banner_makefile(dest/'Makefile',info,has_icon)
    copyfile(TEMPLATES/'setup_lua.py',dest/'setup_lua.py')
    (src/'scene.c').write_text(scene_source(p,images,programs,backgrounds,sounds,meshes,textures),encoding='utf-8')
    # The export is self-contained: copy PNGs and scripts and rewrite paths.
    saved=json.loads(json.dumps(p))
    (dest/'assets').mkdir(exist_ok=True)
    for i,(key,entry) in enumerate(saved['assets'].items()):
        target=f'assets/img_{i}.png'
        original=asset_path(entry['path'],base)
        if original.resolve() != (dest/target).resolve():
            copyfile(original,dest/target)
        entry['path']=target
    layer_defs={}
    for screen in ('top','bottom'):
        if screen in saved['background_layers']:
            layer_defs[f'{screen}0']=saved['background_layers'][screen]
        for i,layer in enumerate(saved.get('extra_background_layers',{}).get(screen,[]),1):
            layer_defs[f'{screen}{i}']=layer
    for key,layer in layer_defs.items():
        target=f'assets/bg_{key}.png'
        original=asset_path(layer['path'],base)
        if original.resolve()!=(dest/target).resolve():copyfile(original,dest/target)
        layer['path']=target
    (dest/'models').mkdir(exist_ok=True)
    for i,(key,entry) in enumerate(saved['mesh_assets'].items()):
        original=(base/entry['path']).resolve()
        target=f'models/mesh_{i}.obj'
        target_path=(dest/target).resolve()
        if original!=target_path:copyfile(original,target_path)
        # Copy local MTL files referenced in OBJ while preserving relative filenames.
        for raw in original.read_text(encoding='utf-8-sig',errors='replace').splitlines():
            parts=raw.strip().split()
            if parts and parts[0]=='mtllib':
                for lib in parts[1:]:
                    srcmtl=(original.parent/lib).resolve()
                    dstmtl=(dest/'models'/lib).resolve()
                    if (srcmtl.is_relative_to(original.parent.resolve()) and
                            dstmtl.is_relative_to((dest/'models').resolve()) and srcmtl.is_file()):
                        dstmtl.parent.mkdir(parents=True,exist_ok=True)
                        if srcmtl!=dstmtl:copyfile(srcmtl,dstmtl)
                        # Copy any PNGs referenced by MTL map_Kd lines.
                        for row in srcmtl.read_text(encoding='utf-8',errors='replace').splitlines():
                            chunks=row.split('#',1)[0].split()
                            if len(chunks)>1 and chunks[0]=='map_Kd':
                                texture_name=' '.join(chunks[1:])
                                sourcetex=(srcmtl.parent/texture_name).resolve()
                                desttex=(dstmtl.parent/texture_name).resolve()
                                if (sourcetex.is_relative_to(srcmtl.parent.resolve()) and
                                        desttex.is_relative_to((dest/'models').resolve()) and sourcetex.is_file()):
                                    desttex.parent.mkdir(parents=True,exist_ok=True)
                                    if sourcetex!=desttex:copyfile(sourcetex,desttex)
        if entry.get('texture'):
            original_texture=asset_path(entry['texture'],base)
            new_tex=f'models/override_{i}.png'
            if original_texture.resolve()!=(dest/new_tex).resolve():copyfile(original_texture,dest/new_tex)
            entry['texture']=new_tex
        entry['path']=target
    (dest/'sounds').mkdir(exist_ok=True)
    for i,(key,info) in enumerate(saved['sounds'].items()):
        target=f'sounds/sound_{i}.wav'
        original=base.joinpath(info['path']).resolve()
        if original != (dest/target).resolve():copyfile(original,dest/target)
        info['path']=target
    (dest/'scripts').mkdir(exist_ok=True)
    exported_scripts={}
    for i,key in enumerate(programs):
        target=f'scripts/script_{i}.lua'
        exported_scripts[key]=target
        original=script_path(key,base)
        if original.resolve()!=(dest/target).resolve():copyfile(original,dest/target)
    for o in saved['objects']:
        if o['script']:o['script']=exported_scripts[o['script']]
    if has_icon:
        copied=dest/'assets'/'project_icon.png'
        copied.parent.mkdir(exist_ok=True)
        original=asset_path(info['icon'],base)
        if original.resolve()!=copied.resolve():copyfile(original,copied)
        saved['metadata']['icon']='assets/project_icon.png'
    (dest/'project.novads.json').write_text(json.dumps(saved,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    reductions=[k for k,v in images.items() if any(f.reduced_colors for f in v)]
    (dest/'HOW_TO_BUILD.txt').write_text(
        'NovaDS Studio v1.1 - NDS banner + experimental Dual 3D + Lua\n\n'
        'To build from NovaDS Studio, use Build ROM (prepares Lua using host Python).\nOpen a devkitPro MSYS2 shell in this folder and run: make\n'
        'Requires devkitARM, libnds, nds-tools and standard DS build tools.\n'
        'ROM: NovaDS_Game.nds (if your toolchain build succeeds).\n\n'
        'Scene data is compiled into ROM: source/scene.c. The core runtime\n'
        '(source/main.c) is identical between projects; PNGs are converted\n'
        'to 4bpp hardware sprites; tile BGs use 4bpp regular / 8bpp affine.\n'
        'Lua scripts are embedded as UTF-8 source and run in a REAL Lua 5.4 VM.\n'
        'If Lua is not prepared, use Windows PowerShell: py -3 setup_lua.py\nFirst Lua preparation downloads/verifies official source (internet required).\n'
        'Offline: place lua-5.4.9.tar.gz beside setup_lua.py before make.\n'
        'This does not load JSON from the DS filesystem at runtime.\n\n'
        'Dual 3D: alternate 3D capture to C/D; no hardware 2D layers in this mode.\n'
        'Tile backgrounds: up to two per 2D screen (one if affine).\n'
        'Painted maps are 32x32 or 64x64 with a 128x128 PNG tileset.\n'
        'Background.scroll and Background.setTransform are available in Lua.\n'
        'UI.print(screen,x,y,text) writes 8x8 console-font text.\n'
        'Controls: D-pad moves controllable sprites; touch moves the first\n' 
        'controllable bottom sprite; START exits.\n'
        'Supported PNG dimensions: each side 8, 16, 32 or 64.\n'
        'Any images with more than 15 colors are quantized to 15.\n'
        f'Quantized assets: {", ".join(reductions) if reductions else "none"}\n',
        encoding='utf-8')
    from .budget import estimate_budget
    report=estimate_budget(p,images,backgrounds,sounds,programs)
    report+='\n3D textures (bank A, 128 KiB):\n'
    for path,tex in textures.items():report+=f'  {path.name}: {tex.width}x{tex.height} direct 16-bit; {tex.width*tex.height*2} bytes\n'
    report+='\n3D mesh assets:\n'
    for key,info in meshes.items():
        verts,faces=info['packed']
        report+=f'  {key}: {len(verts)} vertices / {len(faces)} triangles; approx {len(verts)*6+len(faces)*22} geometry bytes\n'
    report+='\n3D animation clips: %d (ROM-baked transform keys and shared mesh indices)\n' % sum(bool(o.get('animation3d')) for o in p['objects'])
    (dest/'HARDWARE_BUDGET.txt').write_text(report,encoding='utf-8')
    return dest
