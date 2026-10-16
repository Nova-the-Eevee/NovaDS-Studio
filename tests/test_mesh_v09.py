"""NovaDS v0.9 PC-side 3D asset and mesh regression tests."""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from novads.meshassets import parse_obj, simplify, pack_ds
from novads.model import clean_project, load_project
from novads.compiler import export_to

ROOT=Path(__file__).resolve().parents[1]
DEMO=ROOT/'examples'/'3D_Model_Lab_v0.9'/'3D_Model_Lab.novads.json'


class MeshV09(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=load_project(DEMO)
        cls.torus=parse_obj(DEMO.parent/'models/torus.obj')

    def test_parse_and_simplify(self):
        self.assertEqual(len(self.torus.triangles),576)
        reduced=simplify(self.torus,220)
        self.assertGreaterEqual(len(reduced.triangles),180)
        self.assertLessEqual(len(reduced.triangles),220)
        self.assertTrue(all(max(f[:3])<len(reduced.vertices) for f in reduced.triangles))
        verts,faces=pack_ds(reduced)
        self.assertEqual(len(faces),len(reduced.triangles))
        self.assertTrue(all(-32768<=v<=32767 for pt in verts for v in pt))
        self.assertTrue(all(0<=f[3]<=0x7fff for f in faces))

    def test_negative_indices_and_material_colors(self):
        ship=parse_obj(DEMO.parent/'models/ship.obj')
        self.assertEqual(len(ship.triangles),6)
        self.assertEqual(ship.colors['Hull'][0],56)
        self.assertNotEqual(pack_ds(ship)[1][0][3],pack_ds(ship)[1][-1][3])
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'neg.obj'
            file.write_text('v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf -4 -3 -2 -1\n')
            self.assertEqual(len(parse_obj(file).triangles),2)

    def test_validation_budget(self):
        p=load_project(DEMO)
        p['mesh_assets']['torus']['target_triangles']=2
        with self.assertRaises(ValueError):clean_project(p)
        p['mesh_assets']['torus']['target_triangles']=220
        p['mesh_assets']['torus']['path']='../../outside.obj'
        with self.assertRaises(ValueError):clean_project(p)

    def test_portable_full_export_and_gcc(self):
        with tempfile.TemporaryDirectory() as temp:
            export=export_to(Path(temp)/'rom',self.p,DEMO.parent)
            scene=(export/'source/scene.c').read_text()
            runtime=(export/'source/main.c').read_text()
            self.assertIn('const NdMesh nd_meshes[]',scene)
            self.assertIn('draw_mesh',runtime)
            self.assertIn('lua_camera3_position',runtime)
            self.assertIn('lua_camera3_rotation',runtime)
            self.assertTrue((export/'models/mesh_0.obj').exists())
            self.assertTrue((export/'models/mesh_1.obj').exists())
            self.assertTrue((export/'models/ship.mtl').exists())
            self.assertTrue((export/'models/mesh_0.obj').read_text().startswith('# Original'))
            saved=load_project(export/'project.novads.json')
            self.assertEqual(saved['mesh_assets']['torus']['path'],'models/mesh_0.obj')
            self.assertGreater(int(re.search(r'nd_verts_0\[\].*?\{',scene).group(0) is not None),0)
            self.assertIn('3D mesh assets:',(export/'HARDWARE_BUDGET.txt').read_text())
            fake_nds=Path(temp)/'nds.h'
            fake_nds.write_text('#include <stdint.h>\ntypedef uint16_t u16;\n#define RGB15(r,g,b) ((u16)((r)|((g)<<5)|((b)<<10)))\n')
            result=subprocess.run(['gcc','-std=c11','-Werror','-fsyntax-only',
                '-I'+temp,'-I'+str(export/'source'),str(export/'source/scene.c')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
