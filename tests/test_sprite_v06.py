"""v0.6 sprite sheets, animation metadata and backward compatibility."""
import unittest,json,tempfile,subprocess
from pathlib import Path
from novads.model import clean_project,load_project,new_project
from novads.pngassets import convert_sprite_sheet
from novads.compiler import asset_conversion, export_to,scene_source,script_conversion

ROOT=Path(__file__).resolve().parent.parent
DEMO=ROOT/'examples/Sprite_Animation_v0.6/Sprite_Animation.novads.json'
SHEET=DEMO.parent/'assets/nova_4frames.png'

class SpriteAnimationV06(unittest.TestCase):
    def test_sheet_pixels_and_shared_palette(self):
        frames=convert_sprite_sheet(SHEET,16,16)
        self.assertEqual(len(frames),4)
        self.assertEqual({(f.width,f.height) for f in frames},{(16,16)})
        self.assertEqual({f.palette for f in frames},{frames[0].palette})
        self.assertTrue(all(len(f.tiles)==128 for f in frames))
        self.assertNotEqual(frames[0].tiles,frames[1].tiles)
        self.assertEqual(frames[0].palette[0],0)

    def test_sheet_frame_dimensions_rejected(self):
        with self.assertRaisesRegex(ValueError,'exact multiples'):
            convert_sprite_sheet(SHEET,32,32)
        with self.assertRaisesRegex(ValueError,'valid DS'):
            convert_sprite_sheet(SHEET,8,64)

    def test_scene_defaults_keep_v053_compatible(self):
        old=load_project(ROOT/'examples/Tilemap_Parallax_v0.5.3/Tilemap_Parallax.novads.json')
        for obj in old['objects']:
            self.assertEqual(obj['angle'],0)
            self.assertEqual(obj['scale_x'],1)
            self.assertEqual(obj['fps'],0)
            self.assertEqual(obj['frame'],0)
            self.assertFalse(obj['flip_x'])
            self.assertTrue(obj['loop'])

    def test_invalid_sprite_transform_values(self):
        p=new_project('2d2d')
        for prop, val in (('scale_x',0),('angle',float('inf')),('fps',120),('frame',17)):
            test=json.loads(json.dumps(p))
            test['objects'][0][prop]=val
            with self.subTest(prop=prop),self.assertRaises(ValueError):clean_project(test)
        p['assets']['bad']={'path':':builtin/nova.png','frame_width':12,'frame_height':16}
        with self.assertRaisesRegex(ValueError,'frame size'):clean_project(p)

    def test_export_frames_lua_and_metadata(self):
        p=load_project(DEMO);images=asset_conversion(p,DEMO.parent)
        self.assertEqual(len(images['nova_run']),4)
        source=scene_source(p,images,script_conversion(p,DEMO.parent))
        self.assertEqual(source.count('static const u16 nd_tiles_'),5) # original nova + four frames
        self.assertIn('    5, images,',source)
        self.assertRegex(source, r'\b4, 1792, 1, 0, 0, 0, 256, 256, 0')
        with tempfile.TemporaryDirectory() as d:
            out=export_to(Path(d)/'game',p,DEMO.parent)
            scene=(out/'source/scene.c').read_text()
            self.assertIn('static const NdImage images[]',scene)
            self.assertIn('nova', (out/'project.novads.json').read_text())
            r=load_project(out/'project.novads.json')
            self.assertEqual(r['assets']['nova_run']['frame_width'],16)
            self.assertEqual(r['assets']['nova_run']['frame_height'],16)
            self.assertEqual(len(asset_conversion(r,out)['nova_run']),4)
            self.assertEqual((out/'source/main.c').read_bytes(),(ROOT/'templates/main.c').read_bytes())
            self.assertTrue((out/'assets/img_1.png').is_file())
            self.assertIn('oamRotateScale', (out/'source/main.c').read_text())
            self.assertIn('o->frame', (out/'source/main.c').read_text())

    def test_generated_scene_compiles_with_host_header(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);stub=d/'nds.h'
            stub.write_text('#include <stdint.h>\ntypedef uint16_t u16;\n#define RGB15(r,g,b) ((u16)((r)|((g)<<5)|((b)<<10)))\n')
            dest=export_to(d/'rom',load_project(DEMO),DEMO.parent)
            cmd=['gcc','-std=c11','-fsyntax-only','-Werror','-I'+str(d),'-I'+str(dest/'source'),str(dest/'source/scene.c')]
            res=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(res.returncode,0,res.stderr[:2000])

if __name__=='__main__': unittest.main()
