"""Lightweight OBJ + MTL import and deterministic QEM reduction, pure stdlib.

UV-mapped triangulated meshes, map_Kd PNG textures, diffuse colors supported.
An object-local model is centered and scaled into [-1,1] for the DS V16 path.
"""
from dataclasses import dataclass, field
from pathlib import Path
import math
import heapq

MAX_SOURCE_FACES = 12000
MAX_EXPORT_FACES = 1800

@dataclass
class Mesh:
    vertices: list
    triangles: list  # (a,b,c,material_name)
    colors: dict
    uvs: list = field(default_factory=list)  # per exported vertex, or None for missing vt
    textures: dict = field(default_factory=dict)  # material name -> relative PNG path


def _unit_plane(a,b,c):
    u=[b[i]-a[i] for i in range(3)]
    v=[c[i]-a[i] for i in range(3)]
    n=(u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
    m=math.sqrt(sum(x*x for x in n))
    if m < 1e-12:return None
    n=tuple(x/m for x in n)
    return (*n,-sum(n[i]*a[i] for i in range(3)))


def _mtl_materials(path):
    colors={}; textures={}; name=None
    if not path.is_file():return colors,textures
    for raw in path.read_text(encoding='utf-8',errors='replace').splitlines():
        v=raw.split('#',1)[0].split()
        if not v:continue
        if v[0]=='newmtl' and len(v)>1:name=' '.join(v[1:])
        elif v[0]=='Kd' and len(v)>=4 and name:
            try:
                rgb=tuple(max(0,min(255,int(float(x)*255+0.5))) for x in v[1:4])
                colors[name]=rgb
            except ValueError:pass
        elif v[0]=='map_Kd' and name:
            # Only simple relative PNG paths, no option-bearing MTL lines.
            tex=' '.join(v[1:])
            if not tex or tex.startswith('-') or '\\' in tex:continue
            from pathlib import PurePosixPath
            rel=PurePosixPath(tex)
            full=(path.parent/rel).resolve()
            if (rel.suffix.lower()=='.png' and not rel.is_absolute()
                    and '..' not in rel.parts and full.is_relative_to(path.parent.resolve())):
                textures[name]=str(full)
    return colors,textures


def parse_obj(path):
    path=Path(path)
    positions=[];vt=[];faces=[];colors={};textures={};material=''
    # OBJ vertices are indexed separately for position and UV; DS meshes unify them.
    vertices=[];uvs=[];vertex_lookup={}
    for line_no,raw in enumerate(path.read_text(encoding='utf-8-sig',errors='replace').splitlines(),1):
        parts=raw.split('#',1)[0].split()
        if not parts:continue
        typ=parts[0]
        if typ=='v' and len(parts)>=4:
            try:
                v=tuple(float(x) for x in parts[1:4]); assert all(math.isfinite(x) and abs(x)<1e6 for x in v)
            except (ValueError,AssertionError):raise ValueError(f'OBJ line {line_no}: invalid vertex')
            positions.append(v)
            if len(positions)>40000:raise ValueError('OBJ has too many vertices (maximum 40000)')
        elif typ=='vt' and len(parts)>=3:
            try:
                uv=tuple(float(x) for x in parts[1:3]); assert all(math.isfinite(x) and abs(x)<=256 for x in uv)
            except (ValueError,AssertionError):raise ValueError(f'OBJ line {line_no}: invalid UV')
            vt.append(uv)
        elif typ=='usemtl':material=' '.join(parts[1:])
        elif typ=='mtllib':
            for lib in parts[1:]:
                ref=(path.parent/lib).resolve()
                if ref.is_relative_to(path.parent.resolve()):
                    c,t=_mtl_materials(ref);colors.update(c);textures.update(t)
        elif typ=='f':
            if len(parts)<4:continue
            inds=[]
            for token in parts[1:]:
                pieces=token.split('/')
                try:
                    n=int(pieces[0]);idx=n-1 if n>0 else len(positions)+n
                    ti=None
                    if len(pieces)>1 and pieces[1]:
                        num=int(pieces[1]);ti=num-1 if num>0 else len(vt)+num
                except ValueError:raise ValueError(f'OBJ line {line_no}: malformed face index')
                if idx<0 or idx>=len(positions):raise ValueError(f'OBJ line {line_no}: invalid position index')
                if ti is not None and (ti<0 or ti>=len(vt)):
                    raise ValueError(f'OBJ line {line_no}: invalid UV index')
                key=(idx,ti)
                if key not in vertex_lookup:
                    vertex_lookup[key]=len(vertices)
                    vertices.append(positions[idx]);uvs.append(vt[ti] if ti is not None else None)
                inds.append(vertex_lookup[key])
            if len(inds)>64:raise ValueError('OBJ polygon exceeds 64 vertices')
            for k in range(1,len(inds)-1):
                tri=(inds[0],inds[k],inds[k+1],material)
                if len(set(tri[:3]))==3 and _unit_plane(*(vertices[i] for i in tri[:3])):
                    faces.append(tri)
                if len(faces)>MAX_SOURCE_FACES:raise ValueError('OBJ has too many triangles (limit 12000)')
    if not vertices or not faces:raise ValueError('OBJ needs at least one nondegenerate triangle')
    return Mesh(vertices,faces,colors,uvs,textures)


def _qadd(a,b):return tuple(x+y for x,y in zip(a,b))

def _qcost(q,p):
    v=(*p,1.)
    return sum(q[i*4+j]*v[i]*v[j] for i in range(4) for j in range(4))


def _best_position(q,a,b):
    # Minimize p^T Q p, solving upper-left 3x3 system, with stable fallbacks.
    rows=[[q[0],q[1],q[2],-q[3]], [q[4],q[5],q[6],-q[7]], [q[8],q[9],q[10],-q[11]]]
    singular=False
    for col in range(3):
        k=max(range(col,3),key=lambda i:abs(rows[i][col]))
        if abs(rows[k][col])<1e-10:singular=True;break
        rows[col],rows[k]=rows[k],rows[col]
        x=rows[col][col]
        for j in range(col,4):rows[col][j]/=x
        for i in range(3):
            if i==col:continue
            s=rows[i][col]
            for j in range(col,4):rows[i][j]-=s*rows[col][j]
    m=tuple((x+y)*0.5 for x,y in zip(a,b))
    opts=[a,b,m]
    if not singular:
        optimum=tuple(rows[i][3] for i in range(3))
        # Clamp the optimal position to the edge neighborhood to prevent wild spikes.
        length=math.sqrt(sum((a[i]-b[i])**2 for i in range(3)))
        if math.sqrt(sum((optimum[i]-m[i])**2 for i in range(3)))<=max(length*2,1e-5):
            opts.append(optimum)
    return min(opts,key=lambda v:_qcost(q,v))


def _cluster(mesh, resolution):
    """Fast vertex clustering prepass for dense input; avoids giant edge heaps."""
    lows=[min(v[k] for v in mesh.vertices) for k in range(3)]
    highs=[max(v[k] for v in mesh.vertices) for k in range(3)]
    widths=[max(1e-8,highs[k]-lows[k]) for k in range(3)]
    lookup={};positions=[];counts=[];mapping=[]
    for v in mesh.vertices:
        bucket=tuple(min(resolution-1,int((v[k]-lows[k])/widths[k]*resolution)) for k in range(3))
        if bucket not in lookup:
            lookup[bucket]=len(positions);positions.append([0.,0.,0.]);counts.append(0)
        j=lookup[bucket];counts[j]+=1;mapping.append(j)
        for k in range(3):positions[j][k]+=v[k]
    verts=[tuple(x/c for x in v) for v,c in zip(positions,counts)]
    faces=[]
    for a,b,c,mat in mesh.triangles:
        tri=(mapping[a],mapping[b],mapping[c])
        if len(set(tri))==3 and _unit_plane(*(verts[i] for i in tri)):
            faces.append((*tri,mat))
    return Mesh(verts,faces,dict(mesh.colors),[],dict(mesh.textures))


def simplify_lod(mesh, target):
    """Generate a fast *distant* LOD. UV-free meshes use coarse spatial
    clustering before QEM; UV meshes retain QEM seam handling. Targets are
    approximate and can undershoot slightly rather than costing minutes.
    """
    if target >= len(mesh.triangles):
        return mesh
    if target < 4:
        raise ValueError('LOD target must be at least 4 triangles')
    if not any(uv is not None for uv in mesh.uvs) and len(mesh.triangles)>target*1.4:
        candidates=[_cluster(mesh,r) for r in range(3,19)]
        under=[m for m in candidates if 4<=len(m.triangles)<=target]
        if under:
            return max(under,key=lambda m:len(m.triangles))
        over=[m for m in candidates if len(m.triangles)>=target]
        if over:
            reduced=min(over,key=lambda m:len(m.triangles))
            if len(reduced.triangles)<len(mesh.triangles):mesh=reduced
    return simplify(mesh,target)


def simplify(mesh,target):
    """Quadric-error edge collapse with boundary/material-edge protection.

    Target count is best effort: topology, borders, and material seams may halt
    simplification early. Input mesh is never modified.
    """
    if target>=len(mesh.triangles):return Mesh(list(mesh.vertices),list(mesh.triangles),dict(mesh.colors),list(mesh.uvs),dict(mesh.textures))
    if target<4:raise ValueError('Target must be at least 4 triangles')
    if not any(uv is not None for uv in mesh.uvs) and len(mesh.triangles)>2500 and len(mesh.triangles)>target*2:
        # Pick the finest spatial resolution that cuts work to ~2x target,
        # while remaining above target. QEM then performs the quality pass.
        desired=max(target*2,1200)
        lo,hi=3,256
        candidate=mesh
        for _ in range(9):
            mid=(lo+hi)//2
            trial=_cluster(mesh,mid)
            if len(trial.triangles)>desired:hi=mid-1
            else:
                if len(trial.triangles)>=target:candidate=trial
                lo=mid+1
            if lo>hi:break
        if len(candidate.triangles)<len(mesh.triangles):mesh=candidate
    faces=[list(f) for f in mesh.triangles]
    verts=list(mesh.vertices)
    uvs=list(mesh.uvs) if mesh.uvs else [None]*len(verts)
    active=[True]*len(verts)
    quadrics=[[0.0]*16 for _ in verts]
    for a,b,c,_ in faces:
        plane=_unit_plane(verts[a],verts[b],verts[c])
        if plane is None:continue
        q=[plane[i]*plane[j] for i in range(4) for j in range(4)]
        for idx in (a,b,c):
            for k in range(16):quadrics[idx][k]+=q[k]
    # Rebuild graph on each collapse; simpler/safer for small DS-sized meshes.
    # We prioritize edges by QEM cost and constrain boundary/cross-material seams.
    total=len(faces)
    while total>target:
        incident={i:set() for i,ok in enumerate(active) if ok}
        edges={}
        for fi,(a,b,c,mat) in enumerate(faces):
            for v in (a,b,c):incident[v].add(fi)
            for u,v in ((a,b),(b,c),(c,a)):
                key=(min(u,v),max(u,v))
                edges.setdefault(key,[]).append((fi,mat))
        boundary_vertices=set()
        for (a,b),sharing in edges.items():
            if len(sharing)==1:boundary_vertices.update((a,b))
        choices=[]
        for (u,v),sharing in edges.items():
            if len(sharing)!=2 or sharing[0][1]!=sharing[1][1]:continue
            # Protect silhouette boundary vertices against being merged elsewhere.
            if u in boundary_vertices or v in boundary_vertices:
                continue
            q=_qadd(quadrics[u],quadrics[v]);pos=_best_position(q,verts[u],verts[v])
            cost=_qcost(q,pos)
            # Inversion guard: all neighboring faces must retain their orientation.
            good=True
            for fi in incident[u]|incident[v]:
                tri=faces[fi][:3]
                if u in tri and v in tri:continue
                old=_unit_plane(*(verts[i] for i in tri))
                updated=[pos if i in (u,v) else verts[i] for i in tri]
                new=_unit_plane(*updated)
                if old is None or new is None or sum(old[i]*new[i] for i in range(3))<0.15:
                    good=False;break
            if good:heapq.heappush(choices,(cost,u,v,pos))
        if not choices:break
        _,u,v,pos=heapq.heappop(choices)
        if uvs[u] is not None and uvs[v] is not None:
            uvs[u]=((uvs[u][0]+uvs[v][0])*0.5,(uvs[u][1]+uvs[v][1])*0.5)
        verts[u]=pos;quadrics[u]=list(_qadd(quadrics[u],quadrics[v]));active[v]=False
        updated=[]
        for a,b,c,mat in faces:
            tri=[u if i==v else i for i in (a,b,c)]
            if len(set(tri))==3:updated.append([*tri,mat])
        if len(updated)>=total:break
        faces=updated;total=len(faces)
    used=sorted({i for f in faces for i in f[:3]})
    remap={old:i for i,old in enumerate(used)}
    return Mesh([verts[i] for i in used],[(remap[a],remap[b],remap[c],mat) for a,b,c,mat in faces],dict(mesh.colors),[uvs[i] for i in used],dict(mesh.textures))


def pack_ds(mesh, fallback_rgb=(210,170,110)):
    """Return quantized v16 vertices and RGB555 flat-shaded triangle faces."""
    low=[min(p[k] for p in mesh.vertices) for k in range(3)]
    high=[max(p[k] for p in mesh.vertices) for k in range(3)]
    center=[(lo+hi)*0.5 for lo,hi in zip(low,high)]
    extent=max(hi-lo for lo,hi in zip(low,high))
    scale=2.0/extent if extent>1e-10 else 1.0
    points=[tuple((p[i]-center[i])*scale for i in range(3)) for p in mesh.vertices]
    packed=[tuple(max(-32768,min(32767,round(v*4096))) for v in p) for p in points]
    faces=[]
    for a,b,c,mat in mesh.triangles:
        plane=_unit_plane(points[a],points[b],points[c])
        if plane is None:continue
        normal=plane[:3]
        # Baked soft directional light (no DS CPU normal calculations).
        intensity=max(0.32,min(1.,0.54+0.46*(normal[0]*0.40+normal[1]*0.72+normal[2]*0.56)))
        rgb=mesh.colors.get(mat,fallback_rgb)
        col=sum((max(0,min(31,round(rgb[i]*intensity/255*31))) << (i*5)) for i in range(3))
        faces.append((a,b,c,col))
    return packed,faces


def pack_ds_textured(mesh, texture_indices):
    """Geometry with per-face (material texture ID, UVs) in DS 12.4 texel units.

    A negative ID keeps the v0.9 flat-color renderer. Uses per-material resolution
    so models can have multiple different MTL diffuse maps without runtime parsing.
    """
    positions,plain_faces=pack_ds(mesh)
    out=[]
    uv_of=mesh.uvs or [None]*len(mesh.vertices)
    base_colors=iter(plain_faces)
    for a,b,c,mat in mesh.triangles:
        if _unit_plane(mesh.vertices[a],mesh.vertices[b],mesh.vertices[c]) is None:
            continue
        _,_,_,color=next(base_colors)
        tex_id, width, height = texture_indices.get(mat,(-1,0,0))
        coords=[]
        if tex_id>=0 and all(uv_of[k] is not None for k in (a,b,c)):
            # OBJ has V increasing upwards; DS image row order increases downwards.
            # Clamp to source pixels; texture repeat is a later feature.
            for k in (a,b,c):
                u,v=uv_of[k]
                coords.extend((int(round(max(0,min(1,u))*max(0,width-1)*16)),
                               int(round((1-max(0,min(1,v)))*max(0,height-1)*16))))
            # White diffuse tint, retaining v0.9's baked face brightness.
            lit=max(5,min(31,round((((color&31)+((color>>5)&31)+((color>>10)&31))/3))))
            color=lit|(lit<<5)|(lit<<10)
        else:tex_id=-1;coords=[0]*6
        out.append((a,b,c,color,tex_id,*coords))
    return positions,out
