import json
import tempfile
import unittest
from pathlib import Path
from novads.bgassets import convert_background
from novads.model import load_project,clean_project,migrate_v4
from novads.compiler import export_to,background_conversion

ROOT=Path(__file__).resolve().parent.parent
DEMO=ROOT/'examples/Backgrounds_v0.5'

class BackgroundTests(unittest.TestCase):
    def test_bg_converter(self):
        for name in ('meadow','floor'):
            bg=convert_background(DEMO/'assets'/f'{name}.png', affine=(name=='floor'))
            self.assertEqual(len(bg.tilemap),1024)
            self.assertLessEqual(bg.unique_tiles,256)
            self.assertEqual(len(bg.tiles),bg.unique_tiles*(64 if bg.affine else 32))
            self.assertEqual(len(bg.palette),16)
            self.assertTrue(all((index >> 12)==(0 if bg.affine else 1) for index in bg.tilemap))
            self.assertTrue(all((index & 0xff)<bg.unique_tiles for index in bg.tilemap))

    def test_export_contains_background_tables(self):
        p=load_project(DEMO/'Backgrounds.novads.json')
        bgs=background_conversion(p,DEMO)
        self.assertEqual(set(bgs),{'top0','bottom0'})
        with tempfile.TemporaryDirectory() as d:
            exp=export_to(Path(d)/'game',p,DEMO)
            code=(exp/'source/scene.c').read_text()
            self.assertIn('static const NdBackground scene_backgrounds[4]',code)
            self.assertIn('bg_tiles_top0',code)
            self.assertIn('bg_tiles_bottom0',code)
            self.assertIn('1, 0, 0, 0, 256',code) # bottom affine
            self.assertEqual(json.loads((exp/'project.novads.json').read_text())['version'],5)
            self.assertTrue((exp/'assets/bg_top0.png').is_file())

    def test_3d_top_bg_rejected(self):
        p=load_project(DEMO/'Backgrounds.novads.json')
        p['mode']='3d2d'
        p['objects']=[o for o in p['objects'] if o['screen']!='top']
        with self.assertRaisesRegex(ValueError,'Top tile background'):
            clean_project(p)

    def test_no_outside_paths(self):
        p=load_project(DEMO/'Backgrounds.novads.json')
        p['background_layers']['bottom']['path']='../../secret.png'
        with self.assertRaises(ValueError):clean_project(p)

    def test_runtime_api_and_video_modes(self):
        code=(ROOT/'templates/main.c').read_text()
        for expected in ('BgType_ExRotation','MODE_5_2D','bgGetGfxPtr','bgGetMapPtr',
                         'BG_PALETTE_SUB','lua_bg_scroll','lua_bg_transform','lua_ui_print',
                         'consoleInit(&ui_top','consoleInit(&ui_bottom',
                         'VRAM_B_MAIN_BG_0x06000000','bgWrapOn(id)'):
            self.assertIn(expected,code)

    def test_migrate_v4_keeps_scripting(self):
        previous=json.loads((ROOT/'examples/HelloNova_v0.4/HelloNova.novads.json').read_text())
        p=migrate_v4(previous)
        self.assertEqual(p['version'],5)
        self.assertEqual(p['objects'][0]['script'],previous['objects'][0]['script'])
        self.assertEqual(p['background_layers'],{})
