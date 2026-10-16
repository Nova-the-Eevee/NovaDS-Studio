"""Pure-stdlib PNG -> Nintendo DS 4bpp OBJ converter.

Supported: non-interlaced PNG, standard 8-bit RGB/RGBA, grayscale,
gray-alpha and indexed PNG (1/2/4/8-bit indexed). Transparency is
alpha <128. Opaque RGB colors quantize deterministically to <=15 DS colors.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import struct
import zlib

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
SIZES = (8, 16, 32, 64)
VALID_DIMS = {(8,8),(8,16),(8,32),(16,8),(16,16),(16,32),
              (32,8),(32,16),(32,32),(32,64),(64,32),(64,64)}

@dataclass
class DSImage:
    width: int
    height: int
    rgba: bytes
    tiles: bytes
    palette: tuple[int, ...]
    reduced_colors: bool


def read_png(path, *, background=False, sprite_sheet=False, texture=False):
    data = Path(path).read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f'{path}: not a PNG')
    if len(data) > 1024 * 1024:
        raise ValueError('PNG source is over 1 MB (sprite size limit)')
    pos = 8
    hdr = None
    pieces = []
    plte = b''
    trns = b''
    ended = False
    while pos + 12 <= len(data):
        size = struct.unpack_from('>I', data, pos)[0]
        kind = data[pos+4:pos+8]
        start, stop = pos+8, pos+8+size
        if stop+4 > len(data):
            raise ValueError('Truncated PNG chunk')
        chunk = data[start:stop]
        stored_crc = struct.unpack_from('>I', data, stop)[0]
        if zlib.crc32(kind + chunk) & 0xFFFFFFFF != stored_crc:
            raise ValueError('PNG CRC mismatch')
        if kind == b'IHDR':
            if hdr is not None or len(chunk) != 13:
                raise ValueError('Bad PNG header')
            hdr = struct.unpack('>IIBBBBB', chunk)
        elif kind == b'IDAT':
            pieces.append(chunk)
        elif kind == b'PLTE':
            plte = chunk
        elif kind == b'tRNS':
            trns = chunk
        elif kind == b'IEND':
            ended = True
            break
        pos = stop+4
    if not hdr or not ended or not pieces:
        raise ValueError('PNG lacks header, pixels or ending')
    w,h,depth,ctype,compression,filtration,interlace = hdr
    if texture:
        if w not in (8,16,32,64,128) or h not in (8,16,32,64,128):
            raise ValueError(f'Texture {w}x{h} must use power-of-two dimensions 8..128')
    elif sprite_sheet:
        if w > 256 or h > 256 or w < 8 or h < 8 or w % 8 or h % 8:
            raise ValueError('Sprite sheets must have dimensions from 8 to 256, divisible by 8')
    elif (w,h) not in ([(128,128),(256,256)] if background else VALID_DIMS):
        raise ValueError(f'Unsupported PNG dimensions: expected 256x256 background or a DS-sized sprite (got {w}x{h})')
    if compression or filtration or interlace:
        raise ValueError('Only non-interlaced standard PNGs are supported')
    if ctype == 3:
        if depth not in (1,2,4,8):
            raise ValueError('Unsupported indexed PNG bit depth')
        channels = 1
    else:
        if depth != 8 or ctype not in (0,2,4,6):
            raise ValueError('Save the PNG as 8-bit RGB or RGBA (or indexed)')
        channels = {0:1,2:3,4:2,6:4}[ctype]
    stride = (w * channels * depth + 7)//8
    bpp = max(1, (channels*depth+7)//8)
    # Bounded decompression; a 64x64 RGBA PNG needs no more than 16,448 bytes.
    raw_limit = (stride + 1)*h
    comp = b''.join(pieces)
    unpacker = zlib.decompressobj()
    raw = unpacker.decompress(comp, raw_limit+1)
    if len(raw) > raw_limit or not unpacker.eof:
        raise ValueError('PNG decompressed size invalid')
    raw += unpacker.flush()
    if len(raw) != raw_limit:
        raise ValueError('PNG decompressed size incorrect')
    rows = []
    prev = bytearray(stride)
    offset = 0
    for _ in range(h):
        ft = raw[offset]
        cur = bytearray(raw[offset+1:offset+1+stride])
        offset += 1+stride
        for i in range(stride):
            left = cur[i-bpp] if i>=bpp else 0
            up = prev[i]
            upper_left = prev[i-bpp] if i>=bpp else 0
            if ft == 1: v = left
            elif ft == 2: v = up
            elif ft == 3: v = (left+up)//2
            elif ft == 4:
                p = left+up-upper_left
                d = (abs(p-left), abs(p-up), abs(p-upper_left))
                v = (left,up,upper_left)[d.index(min(d))]
            elif ft == 0: v = 0
            else: raise ValueError('Unknown PNG filter')
            cur[i] = (cur[i]+v)&255
        rows.append(cur)
        prev = cur
    rgba = bytearray()
    for row in rows:
        if ctype == 6:
            rgba.extend(row)
        elif ctype == 2:
            trans = tuple(struct.unpack('>HHH',trns)) if len(trns)==6 else None
            for x in range(w):
                r,g,b = row[x*3:x*3+3]
                rgba.extend((r,g,b,0 if trans==(r,g,b) else 255))
        elif ctype == 0:
            transgray = struct.unpack('>H',trns)[0] if len(trns)==2 else -1
            for v in row:
                rgba.extend((v,v,v,0 if v==transgray else 255))
        elif ctype == 4:
            for x in range(w):
                v,a = row[x*2:x*2+2]
                rgba.extend((v,v,v,a))
        else:
            if len(plte)%3 or not plte:
                raise ValueError('Indexed PNG is missing its palette')
            for x in range(w):
                bitpos = x*depth
                index = (row[bitpos//8] >> (8-depth-(bitpos%8))) & ((1<<depth)-1)
                if index*3+3>len(plte):
                    raise ValueError('Indexed PNG references a missing palette color')
                r,g,b = plte[index*3:index*3+3]
                a = trns[index] if index<len(trns) else 255
                rgba.extend((r,g,b,a))
    return w,h,bytes(rgba)


def _pack15(rgb):
    return (rgb[0]>>3) | ((rgb[1]>>3)<<5) | ((rgb[2]>>3)<<10)


def _quantize(colors, max_colors=15):
    """Weighted deterministic median cut in DS RGB555 space."""
    counts = Counter(colors)
    if len(counts) <= max_colors:
        return sorted(counts), False
    groups = [list(counts)]
    while len(groups) < max_colors:
        eligible = []
        for i, group in enumerate(groups):
            if len(group)<2: continue
            ranges = [max((c >> shift)&31 for c in group) - min((c >> shift)&31 for c in group)
                      for shift in (0,5,10)]
            eligible.append((max(ranges)*sum(counts[x] for x in group), i, ranges.index(max(ranges))))
        if not eligible: break
        _, idx, dim = max(eligible)
        group = sorted(groups.pop(idx), key=lambda c: (((c>>(dim*5))&31), c))
        half = sum(counts[c] for c in group)//2
        accum = 0
        split = 1
        for i,c in enumerate(group[:-1],1):
            accum += counts[c]
            if accum >= half:
                split = i
                break
        groups.extend((group[:split],group[split:]))
    centers = []
    for group in groups:
        mass = sum(counts[c] for c in group)
        channels = [round(sum(((c >> shift)&31)*counts[c] for c in group)/mass) for shift in (0,5,10)]
        centers.append(channels[0] | channels[1]<<5 | channels[2]<<10)
    return sorted(set(centers)), True


def _convert_rgba(w,h,rgba,forced_palette=None):
    opaque = []
    pixels = []
    for i in range(0,len(rgba),4):
        if rgba[i+3] < 128:
            pixels.append(None)
        else:
            c = _pack15(rgba[i:i+3]); opaque.append(c); pixels.append(c)
    palette_colors, reduced = _quantize(opaque) if forced_palette is None else (forced_palette, False)
    if not palette_colors:palette_colors = [0]
    def nearest(c):
        a=(c&31,(c>>5)&31,(c>>10)&31)
        return min(range(len(palette_colors)), key=lambda i: sum((a[j]-((palette_colors[i]>>(j*5))&31))**2 for j in range(3)))+1
    lookups = {c:nearest(c) for c in set(opaque)}
    indexed = [0 if p is None else lookups[p] for p in pixels]
    tiles = bytearray()
    for ty in range(h//8):
        for tx in range(w//8):
            for row in range(8):
                for col in range(0,8,2):
                    a=indexed[(ty*8+row)*w+tx*8+col]
                    b=indexed[(ty*8+row)*w+tx*8+col+1]
                    tiles.append(a | (b<<4))
    pal = tuple([0] + list(palette_colors) + [0]*(15-len(palette_colors)))
    assert len(tiles)==w*h//2 and len(pal)==16
    return DSImage(w,h,rgba,bytes(tiles),pal,reduced)


def convert_png(path):
    w,h,rgba = read_png(path)
    return _convert_rgba(w,h,rgba)


def convert_sprite_sheet(path, frame_width, frame_height):
    """Convert 1..16 row-major frames, using one 16-color hardware palette."""
    if (frame_width,frame_height) not in VALID_DIMS:
        raise ValueError('Sprite-sheet frame size must be a valid DS OAM sprite size')
    w,h,rgba=read_png(path,sprite_sheet=True)
    if w%frame_width or h%frame_height:
        raise ValueError('Sheet width/height must be exact multiples of frame dimensions')
    count=(w//frame_width)*(h//frame_height)
    if count<1 or count>16:
        raise ValueError('Sprite sheets support 1 to 16 animation frames')
    colors=[_pack15(rgba[i:i+3]) for i in range(0,len(rgba),4) if rgba[i+3]>=128]
    palette,reduced=_quantize(colors)
    if not palette:palette=[0]
    frames=[]
    for top in range(0,h,frame_height):
        for left in range(0,w,frame_width):
            frame=bytearray()
            for y in range(top,top+frame_height):
                start=(y*w+left)*4
                frame.extend(rgba[start:start+frame_width*4])
            im=_convert_rgba(frame_width,frame_height,bytes(frame),palette)
            im.reduced_colors=reduced
            frames.append(im)
    return tuple(frames)
