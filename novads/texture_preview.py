"""Small optional-dependency-free 3D preview rasterizer for NovaDS Studio.

Unlike the former 4-step-per-triangle approximation, this rasterizes every
covered preview pixel, using the exact quantized UVs exported to the DS.
The depth buffer avoids painting hidden faces on top of visible ones.
It is not a cycle-accurate emulator of the Nintendo DS GPU.
"""
from dataclasses import dataclass
import math
import struct
import zlib


@dataclass
class Raster:
    x: int
    y: int
    width: int
    height: int
    rgba: bytes


def render_mesh(projected, faces, textures, width=256, height=192):
    """Rasterize face tuples created by pack_ds_textured().

    projected: (screen x, screen y, positive camera depth) for each vertex.
    textures: {texture_id: (width, height, RGB5551 pixel tuple)}.
    Returns cropped RGBA pixels + upper-left location, or None.
    """
    pixels = bytearray(width * height * 4)
    zbuffer = [0.] * (width * height)  # reciprocal depth: larger means nearer
    left, top, right, bottom = width, height, -1, -1

    for face in faces:
        a, b, c, color, tex_id, u0, v0, u1, v1, u2, v2 = face
        p, q, r = projected[a], projected[b], projected[c]
        if min(p[2], q[2], r[2]) <= .1:
            continue  # Near clipping is not supported by the small preview.
        ax, ay = p[:2]
        bx, by = q[:2]
        cx, cy = r[:2]
        area = (by-cy)*(ax-cx) + (cx-bx)*(ay-cy)
        if abs(area) < 1e-6:
            continue
        x0 = max(0, int(math.floor(min(ax, bx, cx))))
        y0 = max(0, int(math.floor(min(ay, by, cy))))
        x1 = min(width-1, int(math.ceil(max(ax, bx, cx))))
        y1 = min(height-1, int(math.ceil(max(ay, by, cy))))
        if x1 < x0 or y1 < y0:
            continue
        inv_area = 1. / area
        iz0, iz1, iz2 = 1./p[2], 1./q[2], 1./r[2]
        tex = textures.get(tex_id) if tex_id >= 0 else None
        if tex is not None:
            tw, th, tpixels = tex
            # The exporter stores DS texture coordinates as 12.4 texel values.
            us = (u0 / 16., u1 / 16., u2 / 16.)
            vs = (v0 / 16., v1 / 16., v2 / 16.)
        cr, cg, cb = color & 31, (color >> 5) & 31, (color >> 10) & 31
        for yy in range(y0, y1+1):
            py = yy + .5
            for xx in range(x0, x1+1):
                px = xx + .5
                w0 = ((by-cy)*(px-cx) + (cx-bx)*(py-cy)) * inv_area
                if w0 < -1e-7 or w0 > 1.0000001:
                    continue
                w1 = ((cy-ay)*(px-cx) + (ax-cx)*(py-cy)) * inv_area
                w2 = 1. - w0 - w1
                if w1 < -1e-7 or w2 < -1e-7:
                    continue
                z0, z1, z2 = w0*iz0, w1*iz1, w2*iz2
                invdepth = z0 + z1 + z2
                loc = yy*width + xx
                if invdepth <= zbuffer[loc]:
                    continue
                if tex is not None:
                    # Perspective-correct UVs. This closely matches the intended
                    # hardware texture mapping, unlike affine color sampling.
                    uu = (z0*us[0] + z1*us[1] + z2*us[2]) / invdepth
                    vv = (z0*vs[0] + z1*vs[1] + z2*vs[2]) / invdepth
                    tx = min(tw-1, max(0, int(uu + .5)))
                    ty = min(th-1, max(0, int(vv + .5)))
                    texel = tpixels[ty*tw+tx]
                    if not texel & 0x8000:
                        continue
                    rr = ((texel & 31) * cr * 255 + 480) // (31*31)
                    gg = (((texel >> 5) & 31) * cg * 255 + 480) // (31*31)
                    bb = (((texel >> 10) & 31) * cb * 255 + 480) // (31*31)
                else:
                    rr = cr*255//31
                    gg = cg*255//31
                    bb = cb*255//31
                pos = loc*4
                pixels[pos:pos+4] = bytes((min(255,rr),min(255,gg),min(255,bb),255))
                zbuffer[loc] = invdepth
                left = min(left, xx)
                right = max(right, xx)
                top = min(top, yy)
                bottom = max(bottom, yy)
    if right < left:
        return None
    bw, bh = right-left+1, bottom-top+1
    cropped = bytearray()
    for y in range(top, bottom+1):
        start = (y*width + left)*4
        cropped.extend(pixels[start:start+bw*4])
    return Raster(left, top, bw, bh, bytes(cropped))


def png_rgba(raster):
    """Encode a tiny transparent PNG for tkinter.PhotoImage, no Pillow."""
    def chunk(tag, payload):
        return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', zlib.crc32(tag+payload) & 0xffffffff)
    stride = raster.width*4
    rows = b''.join(b'\0' + raster.rgba[y*stride:(y+1)*stride] for y in range(raster.height))
    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB',raster.width,raster.height,8,6,0,0,0))+
            chunk(b'IDAT', zlib.compress(rows,1)) + chunk(b'IEND',b''))
