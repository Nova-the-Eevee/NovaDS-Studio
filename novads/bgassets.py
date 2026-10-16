"""Nintendo DS 256x256 PNG tile background exporter.

Regular text BG: 4bpp (32 bytes per tile), 16-bit map with palette bank 1.
Extended affine BG: 8bpp (64 bytes per tile), 16-bit map with direct tile IDs.
Both use BG palette slots 17..31 so BG0's console font stays available.
"""
from dataclasses import dataclass
from .pngassets import read_png, _pack15, _quantize

@dataclass
class BackgroundImage:
    tiles: bytes
    tilemap: tuple[int, ...]
    palette: tuple[int, ...]
    reduced_colors: bool
    unique_tiles: int
    affine: bool = False
    map_width: int = 32
    map_height: int = 32


def convert_background(path, *, affine=False):
    w, h, rgba = read_png(path, background=True)
    if (w,h)!=(256,256):raise ValueError("Imported full background must be 256x256")
    opaque = []
    pixels = []
    for i in range(0, len(rgba), 4):
        color = None if rgba[i + 3] < 128 else _pack15(rgba[i:i + 3])
        pixels.append(color)
        if color is not None:
            opaque.append(color)
    pal, reduced = _quantize(opaque)
    if not pal:
        pal = [0]

    def distance(a, b):
        return sum((((a >> (5 * n)) & 31) - ((b >> (5 * n)) & 31)) ** 2 for n in range(3))

    mapping = {c: 1 + min(range(len(pal)), key=lambda n: distance(c, pal[n]))
               for c in set(opaque)}
    indexes = bytes(0 if c is None else mapping[c] for c in pixels)

    tile_size = 64 if affine else 32
    # Tile zero remains transparent and all tiles are deduplicated in VRAM.
    tiles = [bytes(tile_size)]
    seen = {tiles[0]: 0}
    entries = []
    for ty in range(32):
        for tx in range(32):
            tile = bytearray()
            for row in range(8):
                offset = (ty * 8 + row) * w + tx * 8
                if affine:
                    # Extended affine BGs are 8bpp: each pixel is a palette
                    # entry directly. Reserve palette banks 0 / font slots.
                    tile.extend(0 if idx == 0 else idx + 16 for idx in indexes[offset:offset + 8])
                else:
                    # Regular tiled backgrounds support 4bpp + banked palettes.
                    for col in range(0, 8, 2):
                        a, b = indexes[offset + col:offset + col + 2]
                        tile.append(a | (b << 4))
            key = bytes(tile)
            if key not in seen:
                if len(tiles) >= 256:
                    raise ValueError('Background uses more than 256 distinct 8x8 tiles. Simplify the image or reuse patterns.')
                seen[key] = len(tiles)
                tiles.append(key)
            index = seen[key]
            # Extended rotation map is 16bit but palette-bank bits are not
            # used for colors (8bpp), unlike a regular 4bpp text tile map.
            entries.append(index if affine else index | (1 << 12))

    return BackgroundImage(b''.join(tiles), tuple(entries),
                           tuple([0] + pal + [0] * (15 - len(pal))),
                           reduced, len(tiles), affine)


def convert_tilemap(path, layer):
    """Convert a 16x16 atlas of 8x8 tiles (128x128 PNG) + editable world map.

    Tile 0 is reserved as a transparent/empty tile. All other atlas cells
    use their grid-order IDs (1..255). Each layer receives its own palette.
    """
    w,h,rgba=read_png(path,background=True)
    if (w,h)!=(128,128):
        raise ValueError('Painted tilemaps use a 128x128 PNG (16x16 tiles). Tile 0 must be blank.')
    colors=[];pixels=[]
    for i in range(0,len(rgba),4):
        c=None if rgba[i+3]<128 else _pack15(rgba[i:i+3])
        pixels.append(c)
        if c is not None: colors.append(c)
    palette,reduced=_quantize(colors)
    if not palette:palette=[0]
    def dist(a,b):return sum((((a>>(5*j))&31)-((b>>(5*j))&31))**2 for j in range(3))
    cmap={c:1+min(range(len(palette)),key=lambda j:dist(c,palette[j])) for c in set(colors)}
    idx=[0 if c is None else cmap[c] for c in pixels]
    tiles=bytearray(256*32)
    for tile_id in range(1,256):
        tx,ty=(tile_id%16)*8,(tile_id//16)*8
        for row in range(8):
            for col in range(0,8,2):
                at=(ty+row)*128+tx+col
                tiles[tile_id*32+row*4+col//2]=idx[at] | (idx[at+1]<<4)
    mw,mh=layer['map_width'],layer['map_height']
    if layer['affine']:
        raise ValueError('Painted tilemaps are currently regular BGs, not affine BGs')
    return BackgroundImage(bytes(tiles),tuple(tile|(1<<12) for tile in layer['tiles']),
                           tuple([0]+palette+[0]*(15-len(palette))),reduced,256,False,mw,mh)
