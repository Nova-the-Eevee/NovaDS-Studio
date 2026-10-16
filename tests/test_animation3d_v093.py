"""v0.9.3 baked 3D animation, validation, portability, and C table regression."""
import json
import re
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from novads.model import clean_project,load_project,new_project
from novads.compiler import export_to
from novads.meshassets import parse_obj

ROOT=Path(__file__).resolve().parents[1]
DEMO=ROOT/'examples/3D_Animation_Lab_v0.9.3/Animation_Lab.novads.json'

class Animation3DV093(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.project=load_project(DEMO)

    def test_transform_keys_and_mesh_frames(self):
        a=self.project['objects'][0]['animation3d'];b=self.project['objects'][1]['animation3d']
        self.assertEqual(a['name'],'Bounce');self.assertEqual(a['duration'],60)
        self.assertEqual(len(a['keys']),5)
        self.assertEqual(b['mesh_frames'],['blob0','blob1','blob2'])
        self.assertEqual(len(b['keys']),3)

    def test_all_frame_obj_assets_parse(self):
        tris=[]
        for f in range(3):
            mesh=parse_obj(DEMO.parent/f'models/blob_{f}.obj')
            tris.append(len(mesh.triangles))
        self.assertEqual(tris,[12,12,12])

    def test_sorted_keys_and_duplicate_rejection(self):
        p=deepcopy(self.project);clip=p['objects'][0]['animation3d']
        clip['keys'].reverse()
        self.assertEqual(clean_project(p)['objects'][0]['animation3d']['keys'][0]['frame'],0)
        clip['keys'][0]['frame']=clip['keys'][1]['frame']
        with self.assertRaisesRegex(ValueError,'unique'):clean_project(p)

    def test_reject_out_of_range(self):
        p=deepcopy(self.project);p['objects'][0]['animation3d']['keys'][1]['y']=100
        with self.assertRaisesRegex(ValueError,'key y'):clean_project(p)
        p=deepcopy(self.project);p['objects'][0]['animation3d']['fps']=0
        with self.assertRaisesRegex(ValueError,'FPS'):clean_project(p)
        p=deepcopy(self.project);p['objects'][0]['animation3d']['duration']=1
        with self.assertRaisesRegex(ValueError,'duration'):clean_project(p)

    def test_reject_missing_mesh_asset(self):
        p=deepcopy(self.project);p['objects'][1]['animation3d']['mesh_frames'].append('unknown')
        with self.assertRaisesRegex(ValueError,'Mesh-frame'):clean_project(p)

    def test_reject_physics_and_animation_key_conflict(self):
        p=deepcopy(self.project);p['objects'][0]['physics3d']=True
        with self.assertRaisesRegex(ValueError,'physics3d'):clean_project(p)

    def test_2d_legacy_no_animations(self):
        p=clean_project(new_project(mode='2d2d'))
        self.assertTrue(all(obj.get('animation3d') is None for obj in p['objects']))
        with tempfile.TemporaryDirectory() as tmp:
            out=export_to(Path(tmp)/'test',p,ROOT)
            self.assertIn('0, nd_animations3d',(out/'source/scene.c').read_text())

    def test_export_mesh_baked_data_compiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=export_to(Path(tmp)/'rom',self.project,DEMO.parent)
            src=(out/'source/scene.c').read_text()
            self.assertIn('nd_anim_keys_0',src)
            self.assertIn('nd_anim_mesh_1[] = {0, 1, 2}',src)
            self.assertIn('2, nd_animations3d',src)
            self.assertIn('OnAnimationFinished',(out/'source/main.c').read_text())
            self.assertIn('step_animations3d();',(out/'source/main.c').read_text())
            (Path(tmp)/'nds.h').write_text('#include <stdint.h>\ntypedef uint16_t u16;\n#define RGB15(r,g,b) ((u16)((r)|((g)<<5)|((b)<<10)))\n')
            result=subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-fsyntax-only',
                '-I'+tmp,'-I'+str(out/'source'),str(out/'source/scene.c')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_portable_reexport_same_animation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=export_to(Path(tmp)/'rom',self.project,DEMO.parent)
            saved=load_project(out/'project.novads.json')
            self.assertEqual(saved['objects'][1]['animation3d']['mesh_frames'],['blob0','blob1','blob2'])
            self.assertTrue((out/'models/mesh_0.obj').is_file())
            again=export_to(Path(tmp)/'rom2',saved,out)
            first=(out/'source/scene.c').read_text()
            second=(again/'source/scene.c').read_text()
            self.assertEqual(first[first.index('static const NdAnimKey3D nd_anim_keys_0'):],
                             second[second.index('static const NdAnimKey3D nd_anim_keys_0'):])

    def test_lua_methods_and_indices(self):
        c=(ROOT/'templates/main.c').read_text()
        self.assertLess(c.index('static const NdAnim3D *object_anim3d(NdObject *o);'),c.index('static int push_field('))
        self.assertIn('reset_anim3d(o)',c)
        self.assertIn('pauseAnimation',c)
        self.assertIn('resumeAnimation',c)
        self.assertIn('animationSpeed',c)
        self.assertIn('render_scale',c)

if __name__=='__main__':unittest.main()
