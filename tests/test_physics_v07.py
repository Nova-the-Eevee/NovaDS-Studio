"""Physics smoke and schema regressions for NovaDS 0.7."""
import ctypes
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from novads.model import new_project,clean_project,load_project
from novads.compiler import export_to,scene_source,asset_conversion,script_conversion,background_conversion

HERE=Path(__file__).resolve().parent.parent
DEMO=HERE/'examples/Physics_Playground_v0.7/Physics_Playground.novads.json'

class Box(ctypes.Structure):
    _fields_=[('x',ctypes.c_int32),('y',ctypes.c_int32),('w',ctypes.c_int),('h',ctypes.c_int)]

class PhysicsV07(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        out=Path(cls.tmp.name)/'phys.so'
        res=subprocess.run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
                            '-I'+str(HERE/'templates'),str(HERE/'templates/nd_physics.c'),'-o',str(out)],capture_output=True,text=True)
        if res.returncode:raise AssertionError(res.stderr)
        cls.lib=ctypes.CDLL(str(out))
        cls.lib.nd_physics_limit.argtypes=[Box,ctypes.c_int32,ctypes.c_int,Box]
        cls.lib.nd_physics_limit.restype=ctypes.c_int32
        cls.lib.nd_physics_touch.argtypes=[Box,Box]
        cls.lib.nd_physics_touch.restype=ctypes.c_int
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def rect(self,x,y,w,h):return Box(int(x*65536),int(y*65536),w,h)
    def limit(self,body,x,axis,wall):return self.lib.nd_physics_limit(body,int(x*65536),axis,wall)/65536

    def test_floor_and_ceiling_and_wall(self):
        player=self.rect(22,40,16,16)
        self.assertEqual(self.limit(player,130,1,self.rect(0,90,200,8)),74)
        self.assertEqual(self.limit(player,-20,1,self.rect(0,15,200,8)),23)
        self.assertEqual(self.limit(player,190,0,self.rect(70,0,16,200)),54)
        self.assertEqual(self.limit(player,5,0,self.rect(10,0,8,200)),18)
    def test_swept_prevents_tunneling(self):
        self.assertEqual(self.limit(self.rect(0,0,8,8),200,0,self.rect(100,0,8,8)),92)
        self.assertEqual(self.limit(self.rect(150,0,8,8),0,0,self.rect(100,0,8,8)),108)
    def test_off_axis_no_collision(self):
        self.assertEqual(self.limit(self.rect(0,100,16,16),200,0,self.rect(80,0,16,16)),200)
    def test_edge_contacts(self):
        self.assertEqual(self.lib.nd_physics_touch(self.rect(0,0,16,16),self.rect(16,0,16,16)),1)
        self.assertEqual(self.lib.nd_physics_touch(self.rect(0,0,16,16),self.rect(17,0,16,16)),0)
        self.assertEqual(self.lib.nd_physics_touch(self.rect(0,0,16,16),self.rect(16,16,16,16)),0)

    def test_old_project_optin(self):
        p=clean_project(new_project('2d2d'))
        for o in p['objects']:
            self.assertFalse(o['collider'])
            self.assertFalse(o['physics'])
            self.assertEqual(o['collision_layer'],1)
            self.assertEqual(o['collision_mask'],255)

    def test_invalid_physics_rejected(self):
        p=new_project('2d2d')
        for k,v in [('gravity',float('nan')),('velocity_x',5000),('collider_width',500),('collision_layer',0)]:
            obj=json.loads(json.dumps(p));obj['objects'][0][k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):clean_project(obj)
        obj=json.loads(json.dumps(p));obj['objects'][0].update(solid=True,trigger=True)
        with self.assertRaisesRegex(ValueError,'solid and trigger'):clean_project(obj)

    def test_demo_export_and_bitpacking(self):
        p=load_project(DEMO)
        self.assertEqual(p['objects'][0]['gravity'],530)
        self.assertEqual(p['objects'][1]['trigger'],True)
        self.assertEqual(p['background_layers']['bottom']['solid_tile_ids'],[1,2,3])
        src=scene_source(p,asset_conversion(p,DEMO.parent),script_conversion(p,DEMO.parent),background_conversion(p,DEMO.parent))
        self.assertIn('static const unsigned char nd_collision_bottom0[]',src)
        self.assertIn('scene_tile_collisions',src)
        self.assertIn('    { nd_collision_bottom0, 64, 64 },',src)
        with tempfile.TemporaryDirectory() as d:
            export=export_to(Path(d)/'rom',p,DEMO.parent)
            self.assertTrue((export/'source/nd_physics.c').exists())
            self.assertTrue((export/'source/nd_physics.h').exists())
            other=load_project(export/'project.novads.json')
            self.assertEqual(other['objects'][0]['collider_width'],13)
            header=Path(d)/'nds.h'
            header.write_text('#include <stdint.h>\ntypedef uint16_t u16;\n#define RGB15(r,g,b) ((u16)((r)|((g)<<5)|((b)<<10)))\n')
            result=subprocess.run(['gcc','-std=c11','-Werror','-fsyntax-only','-I'+str(d),'-I'+str(export/'source'),str(export/'source/scene.c')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_tilemap_invalid_collision_flags(self):
        p=load_project(DEMO)
        p['background_layers']['bottom']['solid_tile_ids']=[1,300]
        with self.assertRaisesRegex(ValueError,'solid_tile_ids'):clean_project(p)
        p['background_layers']['bottom']['solid_tile_ids']=[1]
        p['background_layers']['bottom']['parallax']=0.2
        with self.assertRaisesRegex(ValueError,'collidable tilemaps'):clean_project(p)

if __name__=='__main__':unittest.main()
