import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class TestMakefileGoals(unittest.TestCase):
    def test_makefile_is_not_lua_prep_only(self):
        for name in ('templates/Makefile', 'example_export/Makefile', 'example_export_2d2d/Makefile'):
            s=(ROOT/name).read_text()
            self.assertIn('.DEFAULT_GOAL := all',s)
            self.assertIn('all: $(BUILD)',s)
            self.assertIn('all: $(OUTPUT).nds',s)
            self.assertIn('$(BUILD): lua-prep',s)

if __name__=='__main__': unittest.main()
