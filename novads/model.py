"""NovaDS v0.4 portable scenes with attached scripts."""
import json
import math
import re
from copy import deepcopy
from pathlib import Path, PurePosixPath

FORMATS = {"3d2d":"3D top + 2D bottom", "2d2d":"2D on both screens", "dual3d":"Dual 3D (experimental, 30 FPS/screen)"}
DEFAULT_ASSET = "nova"


def new_project(mode="3d2d"):
    if mode not in FORMATS:
        raise ValueError('Unknown display mode')
    sprites = [
        {"id":2,"type":"Sprite2D","name":"Nova","screen":"bottom", "x":120,"y":88,
         "speed":2,"controllable":True,"asset":"nova","color":"#FFFFFF"},
        {"id":3,"type":"Sprite2D","name":"Second Nova","screen":"bottom", "x":44,"y":48,
         "speed":0,"controllable":False,"asset":"nova","color":"#FFFFFF"},
    ]
    if mode=='dual3d':
        sprites=[]
        objects=[{'id':1,'type':'Cube3D','name':'Top 3D cube','screen':'top',
                  'x':-0.6,'y':0,'z':0,'size':1.2,'spin':0.8,'color':'#E7A567'},
                 {'id':2,'type':'Cube3D','name':'Bottom 3D cube','screen':'bottom',
                  'x':0.8,'y':0,'z':0,'size':1.4,'spin':-0.6,'color':'#64C5E8'}]
    elif mode=='3d2d':
        objects=[{"id":1,"type":"Cube3D","name":"Rotating Cube","screen":"top",
                  "x":0,"y":0,"z":0,"size":1.55,"spin":1.1,"color":"#F0B475"}] + sprites
    else:
        sprites[1]['screen']='top'
        objects=sprites
    return {"format":"novads-project", "version":5, "name":"Hello Nova", "mode":mode,
            "background_top":"#88B5D4","background_bottom":"#263C58", "mesh_assets":{},
            "metadata":{"description":"","author":"Nova","banner_title":"Hello Nova", "banner_subtitle":"NovaDS v1.1", "banner_creator":"Nova", "icon":""},
            "camera_bottom3d":{"x":1.2,"y":1.2,"z":7,"yaw":-15,"pitch":-10,"fov":65},
            "camera_3d":{"x":0,"y":0,"z":5,"yaw":0,"pitch":0,"fov":65,"frustum_culling":True,"fog_enabled":False,"fog_color":"#62799B","fog_strength":0.65,"brightness":1.0,"profiler":False},
            "assets":{"nova":{"path":":builtin/nova.png"}},"background_layers":{},"extra_background_layers":{},"camera_follow":{},"objects":objects,"scenes":["Main"],"active_scene":"Main","sounds":{}}


def hex_color(value):
    if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):
        raise ValueError('Color must be #RRGGBB')
    return value.upper()


def color_rgb(value):
    v=hex_color(value)
    return tuple(int(v[i:i+2],16) for i in (1,3,5))


def validate_asset_path(path):
    if path == ':builtin/nova.png':
        return path
    if not isinstance(path,str) or not path or '\\' in path or ':' in path or '\0' in path:
        raise ValueError('Asset path must be a relative forward-slash PNG path')
    parts=PurePosixPath(path)
    if parts.is_absolute() or '..' in parts.parts or parts.suffix.lower()!='.png':
        raise ValueError('Invalid asset path (use paths inside the project directory)')
    return path


def clean_project(project):
    if not isinstance(project,dict) or project.get('format')!='novads-project':
        raise ValueError('Not a NovaDS project')
    if project.get('version') != 5:
        raise ValueError('Expected v0.5 project (upgrade older projects in editor)')
    if project.get('mode') not in FORMATS:
        raise ValueError('Unsupported mode (dual 3D not yet implemented)')
    p=deepcopy(project)
    p['name']=str(p.get('name','Untitled'))[:70] or 'Untitled'
    # An NDS banner has three short text lines, plus a separate 32x32 icon.
    # ndstool treats semicolons as line separators, so never pass them as metadata.
    data=p.get('metadata',{})
    if not isinstance(data,dict):raise ValueError('Project properties must be a dictionary')
    metadata={}
    for key,limit,default in [('description',500,''),('author',100,''),
                              ('banner_title',12,p['name'][:12]),
                              ('banner_subtitle',12,'NovaDS v1.1'),
                              ('banner_creator',12,str(data.get('author','Nova'))[:12])]:
        value=data.get(key,default)
        if not isinstance(value,str) or '\x00' in value or '\n' in value or '\r' in value:
            raise ValueError(f'Invalid project {key}')
        if key.startswith('banner_') and (not re.fullmatch(r'[A-Za-z0-9 ._\-]*', value)):
            raise ValueError('NDS banner lines must use plain ASCII, without semicolons or quotes')
        if len(value)>limit:raise ValueError(f'{key} must be at most {limit} characters')
        metadata[key]=value
    icon=data.get('icon','')
    if icon:
        validate_asset_path(icon)
        if icon==':builtin/nova.png': icon=''
    metadata['icon']=icon
    p['metadata']=metadata
    if p['mode']=='dual3d':
        if p.get('background_layers') or p.get('extra_background_layers'):
            raise ValueError('Dual 3D reserves the BG/VRAM banks; remove tile backgrounds')
    
    for key in ('background_top','background_bottom'):
        p[key]=hex_color(p.get(key,'#000000'))
    assets=p.get('assets',{})
    if not isinstance(assets,dict) or len(assets)>64:
        raise ValueError('Expected up to 64 sprite assets')
    normalized={}
    for key,info in assets.items():
        if not isinstance(key,str) or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]{0,39}',key):
            raise ValueError('Asset identifier must use letters, numbers and underscores')
        if not isinstance(info,dict): raise ValueError(f'Invalid asset {key}')
        normalized[key]={'path':validate_asset_path(info.get('path'))}
        if 'frame_width' in info or 'frame_height' in info:
            from .pngassets import VALID_DIMS
            fw=info.get('frame_width');fh=info.get('frame_height')
            if type(fw) is not int or type(fh) is not int or (fw,fh) not in VALID_DIMS:
                raise ValueError(f'{key}: invalid sprite-sheet frame size')
            normalized[key].update(frame_width=fw,frame_height=fh)
    p['assets']=normalized
    meshes=p.get('mesh_assets',{})
    if not isinstance(meshes,dict) or len(meshes)>24:
        raise ValueError('Maximum 24 OBJ mesh assets')
    clean_meshes={}
    for key,entry in meshes.items():
        if not isinstance(key,str) or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]{0,39}',key):
            raise ValueError('Invalid mesh asset identifier')
        if not isinstance(entry,dict):raise ValueError(f'{key}: invalid mesh asset')
        path=entry.get('path','')
        if (not isinstance(path,str) or not path or '\\' in path or ':' in path or '\x00' in path
                or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
                or PurePosixPath(path).suffix.lower()!='.obj'):
            raise ValueError(f'{key}: OBJ path must be relative to project')
        target=entry.get('target_triangles',0)
        if type(target) is not int or not 0<=target<=1800 or (target and target<4):
            raise ValueError(f'{key}: simplification target must be 0 or 4..1800 triangles')
        override=entry.get('texture','')
        if override:validate_asset_path(override)
        lod=entry.get('lod_triangles',0)
        if type(lod) is not int or (lod!=0 and not 4<=lod<=1799):
            raise ValueError(f'{key}: LOD triangles must be 0 or 4..1799')
        clean_meshes[key]={'path':path,'target_triangles':target,'lod_triangles':lod,'texture':override}
    p['mesh_assets']=clean_meshes
    camera=p.get('camera_3d',{})
    if not isinstance(camera,dict):raise ValueError('Invalid 3D camera')
    cam={}
    for key,default,low,high in [('x',0,-24,24),('y',0,-24,24),('z',5,-24,24),
                                  ('yaw',0,-360,360),('pitch',0,-85,85),('fov',65,30,110)]:
        try:v=float(camera.get(key,default))
        except (TypeError,ValueError,OverflowError):raise ValueError(f'Invalid camera {key}')
        if not math.isfinite(v) or not low<=v<=high:raise ValueError(f'Camera {key} out of range')
        cam[key]=v
    cam['frustum_culling']=bool(camera.get('frustum_culling',True))
    cam['fog_enabled']=bool(camera.get('fog_enabled',False))
    cam['fog_color']=hex_color(camera.get('fog_color','#62799B'))
    for key,default,lo,hi in [('fog_strength',0.65,0.0,1.0),('brightness',1.0,0.2,2.0)]:
        try: val=float(camera.get(key,default))
        except (ValueError,TypeError,OverflowError):raise ValueError(f'Invalid {key}')
        if not math.isfinite(val) or not lo<=val<=hi:raise ValueError(f'{key} must be between {lo} and {hi}')
        cam[key]=val
    cam['profiler']=bool(camera.get('profiler',False))
    p['camera_3d']=cam
    bottom=p.get('camera_bottom3d',{})
    if not isinstance(bottom,dict):raise ValueError('Invalid bottom 3D camera')
    bot={}
    for key,default,low,high in [('x',1.2,-24,24),('y',1.2,-24,24),('z',7,-24,24),
                                  ('yaw',-15,-360,360),('pitch',-10,-85,85),('fov',65,30,110)]:
        try:value=float(bottom.get(key,default))
        except (TypeError,ValueError,OverflowError):raise ValueError('Invalid bottom camera '+key)
        if not math.isfinite(value) or not low<=value<=high:raise ValueError('Bottom 3D camera '+key+' out of range')
        bot[key]=value
    p['camera_bottom3d']=bot
    scenes=p.get('scenes',['Main'])
    if not isinstance(scenes,list) or not 1<=len(scenes)<=8 or len(set(scenes))!=len(scenes) or any(
        not isinstance(s,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,23}',s) for s in scenes):
        raise ValueError('Scenes must be 1..8 distinct names using letters, digits, underscores')
    p['scenes']=scenes
    p['active_scene']=p.get('active_scene',scenes[0])
    if p['active_scene'] not in scenes:raise ValueError('Unknown active scene')
    sounds=p.get('sounds',{})
    if not isinstance(sounds,dict) or len(sounds)>16:raise ValueError('Maximum 16 sound assets')
    import pathlib
    normalized_sounds={}
    for key,info in sounds.items():
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,31}',key):
            raise ValueError('Sound identifiers must use letters, digits and underscores')
        if not isinstance(info,dict) or not isinstance(info.get('path'),str):
            raise ValueError(f'Bad WAV asset: {key}')
        rel=info['path']
        if not rel or '\\' in rel or ':' in rel or '\x00' in rel or pathlib.PurePosixPath(rel).is_absolute() or '..' in pathlib.PurePosixPath(rel).parts or pathlib.PurePosixPath(rel).suffix.lower()!='.wav':
            raise ValueError(f'{key}: WAV must be a relative .wav in the project directory')
        normalized_sounds[key]={'path':rel}
    p['sounds']=normalized_sounds
    layers=p.get('background_layers',{})
    extra=p.get('extra_background_layers',{})
    follows=p.get('camera_follow',{})
    if not isinstance(layers,dict) or not isinstance(extra,dict) or not isinstance(follows,dict):
        raise ValueError('Expected background_layers / extra_background_layers / camera_follow dictionaries')
    if any(k not in ('top','bottom') for k in (*layers,*extra,*follows)):
        raise ValueError('Unknown screen in background or camera settings')
    def clean_layer(screen,layer,slot):
        if not isinstance(layer,dict):raise ValueError('Invalid background layer')
        if screen=='top' and p['mode']=='3d2d':
            raise ValueError('Top tile background needs 2D+2D mode; top BG0 is 3D')
        path=validate_asset_path(layer.get('path'))
        if path==':builtin/nova.png': raise ValueError('Use a background / tileset PNG')
        name=str(layer.get('name','layer'+str(slot)))
        if not re.fullmatch('[a-zA-Z_][a-zA-Z0-9_]{0,31}',name):
            raise ValueError('Background layer names use letters/numbers/underscores')
        out={'name':name,'path':path,'affine':bool(layer.get('affine',False))}
        if out['affine'] and slot>0:raise ValueError('Affine background must be the only layer on its screen')
        for k,minimum,maximum,default in [('scroll_x',-32768,32767,0),('scroll_y',-32768,32767,0),
                ('angle',-3600,3600,0),('scale',0.25,4.0,1),('parallax',0,4,1)]:
            try:value=float(layer.get(k,default))
            except (TypeError,ValueError,OverflowError):raise ValueError(f'{screen} background invalid {k}')
            if not math.isfinite(value) or not minimum<=value<=maximum:
                raise ValueError(f'{screen} background {k} outside allowed range')
            out[k]=value
        solid_ids=layer.get('solid_tile_ids',[])
        if not isinstance(solid_ids,list) or len(solid_ids)>256 or any(type(v) is not int or not 0<=v<=255 for v in solid_ids):
            raise ValueError(f'{screen}: solid_tile_ids must be a list of tile IDs 0..255')
        out['solid_tile_ids']=sorted(set(solid_ids))
        if solid_ids and not layer.get('tilemap'):
            raise ValueError(f'{screen}: tile collisions require a painted tilemap')
        if solid_ids and (out['affine'] or out['parallax']!=1 or out['angle']!=0 or out['scale']!=1):
            raise ValueError(f'{screen}: collidable tilemaps must be regular, unrotated and parallax 1')
        if layer.get('tilemap'):
            w=int(layer.get('map_width',32));h=int(layer.get('map_height',32))
            if w not in (32,64) or h not in (32,64) or w!=h:
                raise ValueError('Tilemap dimensions must be square: 32x32 or 64x64')
            tiles=layer.get('tiles')
            if not isinstance(tiles,list) or len(tiles)!=w*h or any(type(v) is not int or v<0 or v>255 for v in tiles):
                raise ValueError(f'Tilemap requires {w*h} tile IDs between 0 and 255')
            out.update(tilemap=True,map_width=w,map_height=h,tiles=tiles[:])
        return out
    normalized_layers={}
    normalized_extra={}
    for screen in ('top','bottom'):
        ex=extra.get(screen,[])
        if not isinstance(ex,list) or len(ex)>1:raise ValueError('Max two layers per screen')
        all_layers=([layers[screen]] if screen in layers else [])+ex
        if len(all_layers)>1 and any(l.get('affine',False) for l in all_layers):
            raise ValueError('An affine background cannot share its screen with another tile layer yet')
        norm=[clean_layer(screen,layer,i) for i,layer in enumerate(all_layers)]
        if len(set(layer['name'] for layer in norm))!=len(norm):
            raise ValueError('Layer names must be unique on each screen')
        if norm:normalized_layers[screen]=norm[0]
        if len(norm)>1:normalized_extra[screen]=norm[1:]
    p['background_layers']=normalized_layers
    p['extra_background_layers']=normalized_extra
    p['camera_follow']={}
    for screen,id_ in follows.items():
        if type(id_) is not int or id_<0:raise ValueError('Camera follow ID must be a nonnegative object ID')
        if id_:p['camera_follow'][screen]=id_
    objects=p.get('objects')
    if not isinstance(objects,list) or len(objects)>192: raise ValueError('Scene must contain 0..192 objects')
    ids=set()
    counts={'top':0,'bottom':0}
    unique={'top':set(),'bottom':set()}
    cubes=0
    meshes_seen=0
    for o in objects:
        if not isinstance(o,dict): raise ValueError('Invalid scene object')
        if type(o.get('id')) is not int or o['id']<=0 or o['id'] in ids:
            raise ValueError('Invalid or duplicate object ID')
        ids.add(o['id'])
        o['scene']=o.get('scene',scenes[0])
        if o['scene'] not in scenes:raise ValueError(f'{o.get("name","Object")}: unknown scene')
        kind=o.get('type'); screen=o.get('screen')
        if kind not in ('Cube3D','Mesh3D','Sprite2D') or screen not in counts:
            raise ValueError('Unknown object type or screen')
        if p['mode']=='dual3d' and kind=='Sprite2D':raise ValueError('Dual 3D has no hardware 2D sprite layer')
        o['name']=str(o.get('name',kind))[:50] or kind
        script=o.get('script','')
        if script:
            if not isinstance(script,str) or not script.endswith('.lua') or '\\' in script or ':' in script or '\0' in script:
                raise ValueError(f'{o["name"]}: script must be a relative .lua path')
            parts=PurePosixPath(script)
            if parts.is_absolute() or '..' in parts.parts:
                raise ValueError(f'{o["name"]}: script must live inside project folder')
        o['script']=script or ''
        o['color']=hex_color(o.get('color','#FFFFFF'))
        if kind in ('Cube3D','Mesh3D'):
            cubes+=1
            if kind=='Mesh3D':
                meshes_seen+=1
                if o.get('mesh') not in clean_meshes:raise ValueError(f'{o["name"]}: missing OBJ mesh asset')
                for key in ('rot_x','rot_y','rot_z'):
                    try:v=float(o.get(key,0))
                    except (ValueError,TypeError,OverflowError):raise ValueError(f'Invalid mesh {key}')
                    if not math.isfinite(v) or abs(v)>3600:raise ValueError(f'Mesh {key} out of range')
                    o[key]=v
            if not (p['mode']=='3d2d' and screen=='top' or p['mode']=='dual3d'): raise ValueError('3D objects require 3D+2D (top) or Dual 3D mode')
            if cubes>160: raise ValueError('Maximum 160 3D objects (GPU budget)')
            for key in ('x','y','z','size','spin'):
                try: v=float(o.get(key,0))
                except (ValueError, TypeError, OverflowError): raise ValueError(f'{o["name"]}: bad {key}')
                if not math.isfinite(v) or not -20<=v<=20: raise ValueError(f'{o["name"]}: {key} outside -20..20')
                o[key]=v
            if not 0<o['size']<=5: raise ValueError('Cube size must be 0..5')
            if abs(o['spin'])>12: raise ValueError('Cube rotation speed must be -12..12')
            o['cull3d']=bool(o.get('cull3d',True))
            try: lod_distance=float(o.get('lod_distance',8.0))
            except (ValueError,TypeError,OverflowError):raise ValueError('Invalid LOD distance')
            if not math.isfinite(lod_distance) or not 1.0<=lod_distance<=49.0:
                raise ValueError('LOD distance must be 1..49 world units')
            o['lod_distance']=lod_distance
            for key in ('collider3d','solid3d','trigger3d','physics3d','sphere3d'):
                o[key]=bool(o.get(key,False))
            if o['solid3d'] and o['trigger3d']:
                raise ValueError(f'{o["name"]}: 3D solid cannot also be a trigger')
            for key in ('half_x3d','half_y3d','half_z3d'):
                try:v=float(o.get(key,o['size']/2))
                except (ValueError,TypeError,OverflowError):raise ValueError(f'{o["name"]}: invalid {key}')
                if not math.isfinite(v) or not 0.05<=v<=20:
                    raise ValueError(f'{o["name"]}: {key} must be 0.05..20 world units')
                o[key]=v
            for key in ('velocity_x3d','velocity_y3d','velocity_z3d','gravity3d','friction3d'):
                try:v=float(o.get(key,0))
                except (ValueError,TypeError,OverflowError):raise ValueError(f'{o["name"]}: invalid {key}')
                if not math.isfinite(v) or not -200<=v<=200 or (key=='friction3d' and v<0):
                    raise ValueError(f'{o["name"]}: {key} out of range')
                o[key]=v
            # v0.9.3: one named, export-baked 3D animation clip per object.
            # All mesh-frame assets are already registered as regular Mesh3D assets.
            clip=o.get('animation3d')
            if clip:
                if not isinstance(clip,dict):raise ValueError('animation3d must be an object')
                name=clip.get('name','Animation')
                if not isinstance(name,str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,31}',name):
                    raise ValueError('Animation name needs letters, digits and underscores')
                fps=clip.get('fps',30)
                if type(fps) not in (int,float) or not math.isfinite(fps) or not 1<=fps<=60:
                    raise ValueError('Animation FPS must be 1..60')
                keys=clip.get('keys',[])
                frames=clip.get('mesh_frames',[])
                if not isinstance(keys,list) or not isinstance(frames,list):raise ValueError('Animation frames/keys must be lists')
                if not keys and not frames:raise ValueError('Animation needs keyframes or mesh frames')
                if len(keys)>64 or len(frames)>16:raise ValueError('Max 64 keys and 16 mesh frames')
                if frames and (kind!='Mesh3D' or any(type(k) is not str or k not in clean_meshes for k in frames)):
                    raise ValueError('Mesh-frame animations require imported Mesh3D assets')
                if o['physics3d'] and keys:
                    raise ValueError('Transform animation on physics-driven 3D objects is not supported; disable physics3d')
                cleaned=[]
                for k in keys:
                    if not isinstance(k,dict):raise ValueError('Animation key must be an object')
                    frame=k.get('frame')
                    if type(frame) is not int or not 0<=frame<=3600:
                        raise ValueError('Animation frame number must be 0..3600')
                    entry={'frame':frame}
                    for field,default,lo,hi in [('x',0,-10,10),('y',0,-10,10),('z',0,-10,10),('yaw',0,-3600,3600),('scale',1,0.1,4)]:
                        v=k.get(field,default)
                        if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:
                            raise ValueError(f'Bad animation key {field}')
                        entry[field]=float(v)
                    cleaned.append(entry)
                if len(set(k['frame'] for k in cleaned))!=len(cleaned):
                    raise ValueError('Animation keyframes must have unique frame numbers')
                cleaned.sort(key=lambda k:k['frame'])
                duration=clip.get('duration',cleaned[-1]['frame'] if cleaned else len(frames)*6)
                if type(duration) is not int or not 1<=duration<=3600 or (cleaned and cleaned[-1]['frame']>duration):
                    raise ValueError('Animation duration must cover all keyframes (1..3600)')
                o['animation3d']={'name':name,'fps':float(fps),'loop':bool(clip.get('loop',True)),
                                  'autoplay':bool(clip.get('autoplay',True)),'duration':duration,
                                  'keys':cleaned,'mesh_frames':frames[:]}
            else:
                o['animation3d']=None
            for key,default,lo,hi in [('collision_layer3d',1,1,255),('collision_mask3d',255,0,255)]:
                v=o.get(key,default)
                if type(v) is not int or not lo<=v<=hi:raise ValueError(f'{o["name"]}: invalid {key}')
                o[key]=v
        else:
            counts[screen]+=1
            if counts[screen]>64: raise ValueError('Maximum 64 sprites per screen in v0.4')
            for key in ('x','y','speed'):
                try: v=int(float(o.get(key,0)))
                except (ValueError,TypeError,OverflowError): raise ValueError(f'{o["name"]}: bad {key}')
                o[key]=v
            if not -512<=o['x']<=512 or not -512<=o['y']<=512: raise ValueError('Sprite position -512..512')
            if not 0<=o['speed']<=12: raise ValueError('Sprite speed 0..12 pixels/frame')
            o['controllable']=bool(o.get('controllable',False))
            if o.get('asset') not in assets:
                raise ValueError(f'{o["name"]}: selected sprite asset is missing')
            for k,low,high,default in [('angle',-3600,3600,0),('scale_x',0.25,4,1),
                  ('scale_y',0.25,4,1),('fps',0,60,0)]:
                try:val=float(o.get(k,default))
                except (TypeError,ValueError,OverflowError):raise ValueError(f'{o["name"]}: invalid {k}')
                if not math.isfinite(val) or not low<=val<=high:
                    raise ValueError(f'{o["name"]}: {k} outside {low}..{high}')
                o[k]=val
            for k in ('flip_x','flip_y','loop'):
                o[k]=bool(o.get(k, k=='loop'))
            try:frame=int(o.get('frame',0))
            except (ValueError,TypeError,OverflowError):raise ValueError('Bad sprite frame index')
            if frame<0 or frame>=16:raise ValueError('Sprite frame must be 0..15')
            o['frame']=frame
            # Physics and colliders are opt-in; old v0.6 scenes keep their behavior.
            for key,default in [('collider',False),('solid',False),('trigger',False),('physics',False)]:
                o[key]=bool(o.get(key,default))
            if o['solid'] and o['trigger']:
                raise ValueError(f'{o["name"]}: collider cannot be both solid and trigger')
            for key,default,minimum,maximum in (
                ('collider_width',0,0,128),('collider_height',0,0,128),
                ('collision_layer',1,1,255),('collision_mask',255,0,255)):
                v=o.get(key,default)
                if type(v) is not int or not minimum<=v<=maximum:
                    raise ValueError(f'{o["name"]}: invalid {key} ({minimum}..{maximum})')
                o[key]=v
            for key,default,minimum,maximum in (
                ('velocity_x',0,-1024,1024),('velocity_y',0,-1024,1024),
                ('gravity',0,-4000,4000),('friction',0,0,4000)):
                try:v=float(o.get(key,default))
                except (ValueError,TypeError,OverflowError):raise ValueError(f'{o["name"]}: invalid {key}')
                if not math.isfinite(v) or not minimum<=v<=maximum:
                    raise ValueError(f'{o["name"]}: {key} outside {minimum}..{maximum}')
                o[key]=v
            unique[screen].add(o['asset'])
    for screen,obj_id in p['camera_follow'].items():
        if obj_id not in ids or not any(o['id']==obj_id and o['type']=='Sprite2D' and o['screen']==screen for o in objects):
            raise ValueError(f'{screen}: camera target must be a Sprite2D on that screen')
    for screen in counts:
        if len(unique[screen])>16:
            raise ValueError(f'Only 16 unique sprite images on the {screen} screen (4bpp palette banks)')
    return p


def save_project(path, project):
    p=clean_project(project)
    Path(path).write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def load_project(path):
    return clean_project(json.loads(Path(path).read_text(encoding='utf-8')))


def next_object_id(project):
    return max((o['id'] for o in project['objects']),default=0)+1


def migrate_v1(old):
    """Converts v0.1 sprite objects to a builtin Nova sprite (appearance may differ)."""
    if old.get('version')!=1 or old.get('format')!='novads-project':
        raise ValueError('Expected a v0.1 project JSON')
    p=deepcopy(old)
    p['version']=5
    p['assets']={'nova':{'path':':builtin/nova.png'}}
    for obj in p['objects']:
        if obj['type']=='Sprite2D': obj['asset']='nova'
    return clean_project(p)


def migrate_v2(old):
    """Upgrade v0.2 without touching IDs, positions, or external assets."""
    if old.get('version')!=2 or old.get('format')!='novads-project':
        raise ValueError('Expected v0.2 project JSON')
    p=deepcopy(old)
    p['version']=5
    for obj in p['objects']: obj.setdefault('script','')
    return clean_project(p)


def migrate_v3(old):
    """Upgrade v0.3 project preserving script files (full Lua compatibility may need edits)."""
    if old.get('version')!=3 or old.get('format')!='novads-project':
        raise ValueError('Expected v0.3 project')
    p=deepcopy(old)
    p['version']=5
    return clean_project(p)


def migrate_v4(old):
    """Upgrade Lua-era v0.4 scenes without touching scripts or external assets."""
    if old.get('version')!=4 or old.get('format')!='novads-project':
        raise ValueError('Expected a v0.4 project')
    p=deepcopy(old)
    p['version']=5
    p.setdefault('background_layers',{})
    return clean_project(p)
