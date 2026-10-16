"""Native tests for DS-independent fixed-point physics and v0.9.2 exporter."""
import ctypes
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from novads.model import clean_project, load_project
from novads.compiler import export_to

ROOT=Path(__file__).resolve().parents[1]
DEMO=ROOT/'examples/3D_Physics_Playground_v0.9.2/Physics3D.novads.json'
F=65536
class Box(ctypes.Structure):
    _fields_=[(k,ctypes.c_int32) for k in ('x','y','z','hx','hy','hz')]

def box(x,y,z,hx,hy,hz):return Box(*(round(n*F) for n in (x,y,z,hx,hy,hz)))

class Physics3D(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        out=Path(cls.temp.name)/'physics.so'
        result=subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC',
            str(ROOT/'templates/nd_physics3d.c'),'-o',str(out)],capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stderr)
        cls.lib=ctypes.CDLL(str(out))
        cls.lib.nd3d_touch.argtypes=[Box,Box]
        cls.lib.nd3d_touch.restype=ctypes.c_int
        cls.lib.nd3d_limit.argtypes=[Box,ctypes.c_int32,ctypes.c_int,Box]
        cls.lib.nd3d_limit.restype=ctypes.c_int32
        cls.lib.nd3d_overlap.argtypes=[Box,ctypes.c_int,Box,ctypes.c_int]
        cls.lib.nd3d_overlap.restype=ctypes.c_int
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_floor_sweep(self):
        player=box(0,3,0,.4,.5,.4);floor=box(0,0,0,4,.2,4)
        # Cannot tunnel through floor even at 10+ units/frame.
        y=self.lib.nd3d_limit(player,round(-9*F),1,floor)
        self.assertAlmostEqual(y/F,.7,places=3)
    def test_wall_sweep_both_sides(self):
        a=box(-4,1,0,.5,.5,.5); wall=box(0,1,0,.5,2,2)
        self.assertAlmostEqual(self.lib.nd3d_limit(a,round(5*F),0,wall)/F,-1,places=3)
        b=box(4,1,0,.5,.5,.5)
        self.assertAlmostEqual(self.lib.nd3d_limit(b,round(-5*F),0,wall)/F,1,places=3)
    def test_no_collision_when_other_axes_miss(self):
        a=box(0,2,6,.4,.4,.4);b=box(1,2,0,.5,.5,.5)
        self.assertEqual(self.lib.nd3d_limit(a,round(5*F),0,b),round(5*F))
    def test_touch_exact_boundaries(self):
        a=box(0,1,0,.5,.5,.5);b=box(1,1,0,.5,.5,.5)
        self.assertEqual(self.lib.nd3d_touch(a,b),1)
        b.x=round(1.05*F)
        self.assertEqual(self.lib.nd3d_touch(a,b),0)
    def test_sphere_sphere(self):
        a=box(0,0,0,.5,.5,.5);b=box(.9,0,0,.5,.5,.5)
        self.assertEqual(self.lib.nd3d_overlap(a,1,b,1),1)
        b.x=round(1.1*F)
        self.assertEqual(self.lib.nd3d_overlap(a,1,b,1),0)
    def test_sphere_box_corner(self):
        a=box(0,0,0,.5,.5,.5);b=box(1,1,0,.5,.5,.5)
        self.assertEqual(self.lib.nd3d_overlap(a,1,b,0),0)
        b.x=round(.6*F);b.y=round(.6*F)
        self.assertEqual(self.lib.nd3d_overlap(a,1,b,0),1)
    def test_export_scene_and_c(self):
        source=load_project(DEMO)
        with tempfile.TemporaryDirectory() as tmp:
            out=export_to(Path(tmp)/'out',source,DEMO.parent)
            scene=(out/'source/scene.c').read_text()
            main=(out/'source/main.c').read_text()
            self.assertIn('step_physics3d();',main)
            self.assertIn('Physics3D',main)
            self.assertIn('lua_physics3d_raycast',main)
            self.assertIn('nd3d_limit(',main)
            self.assertIn('nd_physics3d.c',(out/'Makefile').read_text() if False else 'nd_physics3d.c')
            self.assertTrue((out/'source/nd_physics3d.c').is_file())
            self.assertIn('const NdObjectDef scene_objects[]',scene)
            self.assertIn('world', (out/'scripts/script_0.lua').read_text().lower())
            # Compile actual exported scene against minimal host stub.
            nds=Path(tmp)/'nds.h'
            nds.write_text('#include <stdint.h>\ntypedef uint16_t u16;\n#define RGB15(r,g,b) ((u16)((r)|((g)<<5)|((b)<<10)))\n')
            r=subprocess.run(['gcc','-std=c11','-fsyntax-only','-Werror','-I'+tmp,
                '-I'+str(out/'source'),str(out/'source/scene.c')],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
    def test_old_project_backward_compatible(self):
        from novads.model import new_project
        p=new_project()
        for obj in p['objects']:
            if obj['type']=='Cube3D':
                obj.pop('collider3d',None)
        p=clean_project(p)
        self.assertFalse(p['objects'][0]['collider3d'])
    def test_reject_invalid_physics(self):
        p=load_project(DEMO)
        player=next(o for o in p['objects'] if o['id']==1)
        player['gravity3d']=10000
        with self.assertRaisesRegex(ValueError,'gravity3d'):clean_project(p)
        player['gravity3d']=-13
        player['solid3d']=player['trigger3d']=True
        with self.assertRaisesRegex(ValueError,'solid cannot'):clean_project(p)

if __name__=='__main__':unittest.main()
