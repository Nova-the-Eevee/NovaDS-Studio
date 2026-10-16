"""NovaDS Studio v0.4: no hardware required for tests."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from novads.model import (new_project, clean_project, save_project, load_project,
                          migrate_v1, migrate_v2, migrate_v3, migrate_v4)
from novads.compiler import (export_to, scene_source, asset_conversion,
                             script_conversion)
from novads.pngassets import convert_png
from novads.scripting import validate_script, ScriptError

ROOT=Path(__file__).resolve().parent.parent
DEMO=ROOT/'examples/HelloNova_v0.4'

class NovaDSTests(unittest.TestCase):
    def test_roundtrip(self):
        p=new_project()
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'a.novads.json'
            save_project(f,p)
            self.assertEqual(load_project(f),clean_project(p))
            self.assertEqual(p['version'],5)

    def test_basic_exports(self):
        for mode in ('2d2d','3d2d'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
                dest=export_to(Path(d)/'game',new_project(mode))
                c=(dest/'source/scene.c').read_text()
                self.assertIn('NdScript scene_scripts',c)
                self.assertIn('const NdScene nd_scene',c)
                self.assertIn('nd_tiles_0',c)
                self.assertEqual(json.loads((dest/'project.novads.json').read_text())['version'],5)
                self.assertTrue((dest/'setup_lua.py').is_file())
                self.assertTrue((dest/'source/main.c').is_file())
                self.assertIn('lua-prep:',(dest/'Makefile').read_text())

    def test_png_conversion(self):
        im=convert_png(ROOT/'novads/assets/nova.png')
        self.assertEqual((im.width,im.height),(16,16))
        self.assertEqual(im.palette[0],0)
        self.assertEqual(len(im.tiles),128)
        self.assertEqual(len(im.palette),16)

    def test_shared_image(self):
        p=new_project()
        c=scene_source(p,asset_conversion(p,ROOT))
        self.assertEqual(c.count('static const u16 nd_tiles_'),1)

    def test_invalid_scene(self):
        p=new_project('2d2d')
        p['objects'].append(dict(p['objects'][0],id=99,type='Cube3D'))
        with self.assertRaises(ValueError):clean_project(p)

    def test_invalid_png_path(self):
        p=new_project();p['assets']['nova']['path']='../../outside.png'
        with self.assertRaises(ValueError):clean_project(p)

    def test_palette_limit(self):
        p=new_project()
        p['assets']={f'img{i}':{'path':':builtin/nova.png'} for i in range(17)}
        p['objects']=[dict(p['objects'][1],id=i+1,asset=f'img{i}') for i in range(17)]
        with self.assertRaises(ValueError):clean_project(p)

    def test_migrate_legacy(self):
        p=new_project()
        old3=dict(p,version=3)
        self.assertEqual(migrate_v3(old3)['version'],5)
        old2=dict(p,version=2)
        self.assertEqual(migrate_v2(old2)['version'],5)
        for o in old2['objects']:o.pop('script',None)
        self.assertEqual(migrate_v2(old2)['objects'][0]['script'],'')
        old4=dict(p,version=4)
        self.assertEqual(migrate_v4(old4)['version'],5)
        old1=dict(p,version=1)
        self.assertEqual(migrate_v1(old1)['version'],5)

    def test_real_lua_features(self):
        source='''local nums={1,2,3}\nlocal total=0\nlocal function foo(n)\n  for i=1,n do total=total+nums[i] end\nend\nfunction Update(dt) foo(3); self.x=self.x+total*dt end'''
        result=validate_script(source)
        self.assertTrue(result)
        self.assertNotIn('subset',result)

    def test_real_parser_rejects_bad_syntax_if_available(self):
        result=validate_script('local x = 5')
        if 'syntax OK' not in result:self.skipTest('no local Lua executable/library')
        with self.assertRaises(ScriptError):validate_script('function Update(dt) local x = end')

    def test_script_source_exported_exactly(self):
        p=migrate_v4(json.loads((DEMO/'HelloNova.novads.json').read_text()))
        with tempfile.TemporaryDirectory() as d:
            export=export_to(Path(d)/'rom',p,DEMO)
            c=(export/'source/scene.c').read_text()
            scripts=script_conversion(p,DEMO)
            for index,(path,text) in enumerate(scripts.items()):
                self.assertIn(f'static const unsigned char lua_script_{index}[]',c)
                self.assertIn('lua_script_'+str(index)+', '+str(len(text.encode('utf-8'))),c)
                self.assertTrue((export/f'scripts/script_{index}.lua').is_file())
                self.assertEqual((export/f'scripts/script_{index}.lua').read_text(),text)
            self.assertNotIn('NdInstr',c)
            self.assertIn('scene_scripts',c)
            self.assertEqual((export/'source/main.c').read_bytes(),
                             (ROOT/'templates/main.c').read_bytes())

    def test_script_traversal_rejected(self):
        p=new_project();p['objects'][0]['script']='../../evil.lua'
        with self.assertRaises(ValueError):clean_project(p)

    def test_missing_script_rejected(self):
        p=new_project();p['objects'][0]['script']='scripts/no.lua'
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):export_to(Path(d)/'rom',p,d)

    def test_embedded_source(self):
        p=new_project()
        p['objects'][0]['script']='scripts/test.lua'
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'scripts').mkdir()
            (d/'scripts/test.lua').write_text('local foo="☀"\nfunction Update(dt) end\n')
            c=scene_source(p,asset_conversion(p,d),script_conversion(p,d))
            self.assertIn('226, 152, 128',c)
            self.assertIn('scene_scripts',c)

    def test_bounded_script(self):
        with self.assertRaises(ScriptError):validate_script('x' * 30000)
        with self.assertRaises(ScriptError):validate_script('local x="a\x00b"')

    def test_official_lua_checksum_pinned(self):
        txt=(ROOT/'templates/setup_lua.py').read_text()
        self.assertIn('2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6',txt)
        self.assertIn('5.4.9',txt)

    def test_runtime_contains_vm(self):
        c=(ROOT/'templates/main.c').read_text()
        self.assertIn('lua_newstate(',c)
        self.assertIn('luaL_loadbufferx(',c)
        self.assertIn('lua_pcall(',c)
        self.assertIn('lua_sethook(',c)
        self.assertIn('lua_newuserdatauv(',c)
        self.assertIn('lua_gc(',c)
        self.assertNotIn('run_instructions',c)

if __name__=='__main__':unittest.main()
