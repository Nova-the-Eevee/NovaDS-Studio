"""v1.0 full-game integration and DS scene replay regressions."""
import unittest
import tempfile
import subprocess
import ctypes
import ctypes.util
from pathlib import Path
from novads.model import load_project, clean_project
from novads.compiler import export_to, mesh_conversion
from novads.scripting import validate_script

ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/'examples'/'Novas_Star_Trail_v1.0'/'Novas_Star_Trail.novads.json'

class TestStarTrail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project=load_project(GAME)

    def test_game_has_real_start_finish_and_retry(self):
        p=self.project
        self.assertEqual(p['scenes'],['Title','Level','Win','Lose'])
        self.assertEqual(p['active_scene'],'Title')
        for scene in p['scenes']:
            self.assertTrue(any(o['scene']==scene and o.get('script') for o in p['objects']),scene)
        self.assertEqual({o['id'] for o in p['objects'] if o['scene']=='Level' and o.get('trigger3d')},{20,21,22,30,40,41})
        self.assertTrue(any(o['scene']=='Level' and o.get('physics3d') for o in p['objects']))
        self.assertTrue(any(o['scene']=='Level' and o.get('solid3d') for o in p['objects']))

    def test_all_scripts_are_real_lua(self):
        for filename in sorted((GAME.parent/'scripts').glob('*.lua')):
            with self.subTest(filename=filename.name):
                r=validate_script(filename.read_text(encoding='utf-8'))
                self.assertIn('syntax',r.lower())

    def test_physics_animation_texture_and_audio_in_one_game(self):
        p=self.project
        self.assertEqual(set(p['sounds']),{'start','collect','ouch','win'})
        self.assertTrue(any(o.get('animation3d') for o in p['objects']))
        self.assertTrue(any(o['type']=='Mesh3D' for o in p['objects']))
        self.assertTrue(any(o['type']=='Sprite2D' for o in p['objects']))
        self.assertTrue(any(o['scene']=='Level' and o.get('collider3d') for o in p['objects']))
        meshes,textures=mesh_conversion(p,GAME.parent)
        self.assertIn('fox',meshes)
        self.assertIn('grass',meshes)
        self.assertTrue(textures)
        self.assertLess(sum(len(x['packed'][1]) for k,x in meshes.items()),1500)

    def test_reentry_restores_mutable_colliders(self):
        c=(ROOT/'templates'/'main.c').read_text()
        block=c[c.index('static void perform_scene_change'):c.index('int main(void)')]
        for phrase in ('o->collider3d=o->def.collision3d','o->trigger3d=o->def.trigger3d',
                       'o->physics3d=o->def.physics3d','o->visible=true',
                       'o->collider=o->def.collider','o->angle='):
            with self.subTest(phrase=phrase):self.assertIn(phrase,block)

    def test_portable_export_and_generated_c(self):
        with tempfile.TemporaryDirectory() as d:
            dest=export_to(Path(d)/'rom',self.project,GAME.parent)
            header=(dest/'source/novads_runtime.h').read_text()
            scene=(dest/'source/scene.c').read_text()
            self.assertIn('animation3d_count',header)
            self.assertIn('nd_scene',scene)
            self.assertTrue((dest/'models/grass.png').exists())
            self.assertTrue((dest/'scripts/script_0.lua').exists())
            (Path(d)/'nds.h').write_text('#include <stdint.h>\ntypedef uint16_t u16;\n#define RGB15(r,g,b) ((u16)((r)|((g)<<5)|((b)<<10)))\n')
            r=subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-fsyntax-only',
                        '-I'+d,'-I'+str(dest/'source'),str(dest/'source/scene.c')],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            second=load_project(dest/'project.novads.json')
            other=export_to(Path(d)/'second',second,dest)
            # The script locator comments and embedded names intentionally change
            # after copying; geometry and material payloads must remain identical.
            a=(dest/'source/scene.c').read_text()
            b=(other/'source/scene.c').read_text()
            marker='static const NdMeshVertex nd_verts_0'
            self.assertIn(marker,a)
            self.assertEqual(a[a.index(marker):],b[b.index(marker):])

    def test_real_lua_gameplay_flow(self):
        """Execute Lua on the host with mocked DS APIs; no emulator claim."""
        name=ctypes.util.find_library('lua5.4')
        if not name:self.skipTest('Native Lua 5.4 library unavailable')
        lib=ctypes.CDLL(name)
        lib.luaL_newstate.restype=ctypes.c_void_p
        lib.luaL_openlibs.argtypes=[ctypes.c_void_p]
        lib.luaL_loadbufferx.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_char_p]
        lib.luaL_loadbufferx.restype=ctypes.c_int
        lib.lua_pcallk.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_longlong,ctypes.c_void_p]
        lib.lua_pcallk.restype=ctypes.c_int
        lib.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p]
        lib.lua_tolstring.restype=ctypes.c_char_p
        lib.lua_close.argtypes=[ctypes.c_void_p]
        def run(source):
            L=lib.luaL_newstate()
            if not L:self.fail('Lua could not allocate state')
            try:
                lib.luaL_openlibs(L)
                data=source.encode('utf-8')
                status=lib.luaL_loadbufferx(L,data,len(data),b'@test.lua',b't')
                if status==0:status=lib.lua_pcallk(L,0,0,0,0,None)
                error=lib.lua_tolstring(L,-1,None) if status else None
                self.assertEqual(status,0,error.decode(errors='replace') if error else 'Lua failed')
            finally:lib.lua_close(L)
        stub="""
local loads={}
UI={clear=function(...) end,print=function(...) end,bar=function(...) end,
    button=function(...) return false end}
Audio={play=function(...) end}
Input={pressed=function(...) return false end,isDown=function(...) return false end}
Camera3D={setPosition=function(...) end,setRotation=function(...) end}
Physics3D={raycast=function(...) return nil end}
Scene={load=function(name) table.insert(loads,name) end}
self={id=1,x=0,y=1,z=3,vx=0,vy=0,vz=0,grounded=true}
"""
        player=(GAME.parent/'scripts/player.lua').read_text()
        scenario="""
Start()
local gate={id=30,collider=true,visible=true}
OnCollisionEnter(gate)
assert(#loads==0,'gate should be locked')
for _,id in ipairs({20,21,22}) do
    local item={id=id,collider=true,visible=true}
    OnCollisionEnter(item)
    assert(item.collider==false and item.visible==false,'item not collected')
end
OnCollisionEnter(gate)
assert(loads[#loads]=='Win','gate did not open after three crystals')
assert(StarTrailTime~=nil)
"""
        run(stub+player+'\n'+scenario)
        # Hazard loss path also works without collecting all crystals.
        run(stub+player+'\nStart()\nOnCollisionEnter({id=40,collider=true})\nassert(loads[#loads]=="Lose")')
