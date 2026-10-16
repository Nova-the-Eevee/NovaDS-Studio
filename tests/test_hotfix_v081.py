import pathlib, unittest
from novads.compiler import ROOT

class HotfixTests(unittest.TestCase):
    def test_affine_scene_hidden_without_assert(self):
        main = (ROOT / 'templates' / 'main.c').read_text()
        self.assertNotRegex(main.split('static void render_sprites(void) {')[1].split('static void perform_scene_change')[0], r'(?m)^\s*oamSetHidden\(')
        self.assertIn('oamClearSprite(', main)
    def test_bg_lua_show(self):
        main=(ROOT / 'templates' / 'main.c').read_text()
        self.assertIn('static int lua_bg_show(',main)
        self.assertIn('lua_bg_show);lua_setfield(L,-2,"show")',main)
