"""Offline Nintendo DS direct RGB5551 3D texture converter, no Pillow required.

15 bits of color + 1 bit alpha, in row-major native VRAM texel order.
"""
from dataclasses import dataclass
from .pngassets import read_png

MAX_TEXTURE_BYTES=128*1024  # VRAM bank A; B is reserved for main-screen OBJ.

@dataclass
class DSTexture:
    width:int
    height:int
    pixels:tuple


def convert_texture(path):
    w,h,rgba=read_png(path,texture=True)
    pixels=[]
    for i in range(0,len(rgba),4):
        r,g,b,a=rgba[i:i+4]
        # GL_RGBA: bit15 is alpha, unlike palette background RGB555.
        pixels.append((r>>3)|((g>>3)<<5)|((b>>3)<<10)|(0x8000 if a>=128 else 0))
    return DSTexture(w,h,tuple(pixels))
