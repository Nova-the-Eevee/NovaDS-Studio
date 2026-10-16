"""v0.9.4 rendering budget, LOD, color and visibility regressions."""
import unittest
from copy import deepcopy
from pathlib import Path
import tempfile
import subprocess
import math
from novads.model import load_project,clean_project
from novads.compiler import mesh_conversion,export_to,scale_rgb555

ROOT=Path(__file__).resolve().parents[1]
DEMO=ROOT/'examples/3D_Optimization_Lab_v0.9.4/Optimization_Lab.novads.json'

class TestOptimization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.p=load_project(DEMO)

    def test_defaults_backwards_compatible(self):
        old=load_project(ROOT/'examples/3D_Animation_Lab_v0.9.3/Animation_Lab.novads.json')
        self.assertTrue(old['camera_3d']['frustum_culling'])
        self.assertFalse(old['camera_3d']['fog_enabled'])
        self.assertEqual(old['camera_3d']['brightness'],1.0)
        self.assertTrue(all(o.get('cull3d',True) for o in old['objects'] if o['type']!='Sprite2D'))

    def test_project_settings_validation(self):
        for name,value in [('fog_color','#GGGGGG'),('fog_strength',1.5),('brightness',0.0)]:
            p=deepcopy(self.p);p['camera_3d'][name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):clean_project(p)
        p=deepcopy(self.p);p['mesh_assets']['torus']['lod_triangles']=-1
        with self.assertRaises(ValueError):clean_project(p)
        p=deepcopy(self.p);p['objects'][0]['lod_distance']=100
        with self.assertRaises(ValueError):clean_project(p)

    def test_lod_mesh_is_smaller_and_shared(self):
        meshes,_=mesh_conversion(self.p,DEMO.parent)
        self.assertIn('torus__LOD',meshes)
        hi=len(meshes['torus']['packed'][1]);low=len(meshes['torus__LOD']['packed'][1])
        self.assertGreater(hi,low)
        self.assertLessEqual(low,60)

    def test_brightness_saturates(self):
        self.assertEqual(scale_rgb555(0x7fff,2),0x7fff)
        self.assertEqual(scale_rgb555(0x7fff,0),0)
        self.assertEqual(scale_rgb555(0x4210,1),0x4210)

    def test_export_indices_and_host_scene(self):
        with tempfile.TemporaryDirectory() as td:
            out=export_to(Path(td)/'rom',self.p,DEMO.parent)
            src=(out/'source/scene.c').read_text()
            header=(out/'source/novads_runtime.h').read_text()
            self.assertIn('lod_mesh_index',header)
            self.assertIn('nd_meshes',src)
            self.assertIn('frustum_culling',header)
            self.assertIn('nd_scene',src)
            (Path(td)/'nds.h').write_text('#include <stdint.h>\ntypedef uint16_t u16;\n#define RGB15(r,g,b) ((u16)((r)|((g)<<5)|((b)<<10)))\n')
            result=subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+td,
                                   '-I'+str(out/'source'),str(out/'source/scene.c')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            back=load_project(out/'project.novads.json')
            self.assertEqual(back['mesh_assets']['torus']['lod_triangles'],60)
            self.assertTrue(back['camera_3d']['profiler'])
            again=export_to(Path(td)/'again',back,out)
            first=(out/'source/scene.c').read_text()
            second=(again/'source/scene.c').read_text()
            self.assertEqual(first[first.index('static const NdMeshVertex nd_verts_0'):],
                             second[second.index('static const NdMeshVertex nd_verts_0'):])

    def test_visibility_fixed_point_units_and_no_physics_culling(self):
        c=(ROOT/'templates/main.c').read_text()
        for needle in ('camera3_x/4096.0f','camera3_y/4096.0f','camera3_z/4096.0f',
                       'o->x/65536.0f','o->y/65536.0f','o->z/65536.0f',
                       'sphere_visible(depth,side,up,bound3d(o),&view)',
                       'stat_culled++','stat_lod++','glFlush(0)'):
            self.assertIn(needle,c)
        self.assertLess(c.index('step_physics3d();'),c.index('render_3d();'))

if __name__=='__main__':unittest.main()
