"""Regression for real ARM GCC: registry reference must be declared before raycast."""
import tempfile
import unittest
from pathlib import Path
from novads.compiler import export_to
from novads.model import load_project

ROOT = Path(__file__).resolve().parents[1]


def check_order(source):
    decl = 'static int object_table_ref=LUA_NOREF;'
    start = 'static int lua_physics3d_raycast(lua_State *L)'
    lookup = 'lua_rawgeti(L,LUA_REGISTRYINDEX,object_table_ref);'
    assert source.count(decl) == 1, 'Missing or duplicate registry variable'
    assert source.index(decl) < source.index(start), 'Registry variable declared after raycast'
    assert source.index(start) < source.index(lookup), 'Raycast body not found'

class RegistryOrder(unittest.TestCase):
    def test_template(self):
        check_order((ROOT/'templates/main.c').read_text())

    def test_all_bundled_exports(self):
        samples = list(ROOT.glob('example_export*/source/main.c'))
        self.assertGreaterEqual(len(samples), 1)
        for src in samples:
            with self.subTest(src=src): check_order(src.read_text())

    def test_fresh_export(self):
        demo = ROOT/'examples/3D_Physics_Playground_v0.9.2/Physics3D.novads.json'
        project = load_project(demo)
        with tempfile.TemporaryDirectory() as folder:
            output = export_to(Path(folder)/'out', project, demo.parent)
            check_order((output/'source/main.c').read_text())

if __name__ == '__main__': unittest.main()
