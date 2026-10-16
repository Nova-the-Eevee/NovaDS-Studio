"""Verify DS BG encoding by independently reading each emitted tile & map."""
from pathlib import Path
import unittest
from novads.bgassets import convert_background
from novads.pngassets import read_png, _pack15
from novads.compiler import background_conversion
from novads.model import load_project

ROOT=Path(__file__).resolve().parent.parent
DEMO=ROOT/'examples/Backgrounds_v0.5'


def pixel_from_vram_data(bg, x, y):
    index = bg.tilemap[(y//8)*32 + (x//8)] & 1023
    width = 64 if bg.affine else 32
    base = width*index
    row = (y % 8)*8 + x%8
    if bg.affine:
        # One byte per pixel, direct BG palette entry index.
        return bg.tiles[base+row]
    value=bg.tiles[base+row//2]
    bank=(bg.tilemap[(y//8)*32 + (x//8)]>>12)&15
    return (value>>((row%2)*4)&15) + bank*16

class HardwareFormatTests(unittest.TestCase):
    def test_regular_and_affine_tile_decoding_matches_source(self):
        for name,affine in [('meadow',False),('floor',True)]:
            source=DEMO/'assets'/f'{name}.png'
            b=convert_background(source,affine=affine)
            w,h,rgba=read_png(source,background=True)
            self.assertEqual((w,h),(256,256))
            for y in range(256):
                for x in range(256):
                    rgba_off=(y*w+x)*4
                    if rgba[rgba_off+3]<128:
                        wanted=0
                    else:
                        c=_pack15(rgba[rgba_off:rgba_off+3])
                        wanted=17+min(range(15), key=lambda n:
                            sum(( ( (c>>(5*j))&31) - ((b.palette[n+1]>>(5*j))&31))**2
                                for j in range(3)) if b.palette[n+1] else 999999)
                    actual=pixel_from_vram_data(b,x,y)
                    self.assertEqual(actual,wanted,(name,affine,x,y))
            # 4bpp pixels must map to bank 1; affine BG map's palette bits unused.
            self.assertTrue(all((entry>>12)==(0 if affine else 1) for entry in b.tilemap))
            self.assertEqual(len(b.tiles),b.unique_tiles*(64 if affine else 32))

    def test_exporter_switches_tile_format_based_on_mode(self):
        project=load_project(DEMO/'Backgrounds.novads.json')
        bgs=background_conversion(project,DEMO)
        self.assertFalse(bgs['top0'].affine)
        self.assertTrue(bgs['bottom0'].affine)
        self.assertEqual(bgs['top0'].tilemap[0]>>12,1)
        self.assertEqual(bgs['bottom0'].tilemap[0]>>12,0)

    def test_main_bg_bank_has_correct_vram_window(self):
        code=(ROOT/'templates/main.c').read_text()
        self.assertIn('vramSetBankB(VRAM_B_MAIN_BG_0x06000000);',code)
        self.assertNotIn('vramSetBankB(VRAM_B_MAIN_BG);',code)
        self.assertIn('BgType_ExRotation',code)
        self.assertIn('bgWrapOn(id)',code)
