"""Regression tests for the MSYS2 environment that does not have Python."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class NoMsysPythonTests(unittest.TestCase):
    def _fixture(self, folder):
        """Extract only the Lua preparation rule, without requiring devkitARM."""
        mk = (ROOT / 'templates' / 'Makefile').read_text(encoding='utf-8')
        required = re.search(r'^LUA_REQUIRED := (.+)$', mk, re.M)
        self.assertIsNotNone(required)
        target = re.search(r'^lua-prep:\n((?:\t.*\n)+)', mk, re.M)
        self.assertIsNotNone(target)
        text = 'LUA_REQUIRED := '+required.group(1)+'\n.PHONY: lua-prep\n'+'lua-prep:\n'+target.group(1)
        (folder / 'Makefile').write_text(text, encoding='utf-8')
        return required.group(1).split()

    def test_prepared_lua_does_not_require_python_in_path(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            req=self._fixture(root)
            for name in req:
                file=root/name
                file.parent.mkdir(parents=True,exist_ok=True)
                file.write_bytes(b'dummy')
            result=subprocess.run([shutil.which('make'), 'lua-prep'],cwd=root,env={'PATH':''},
                                  text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode,0,result.stdout)
            self.assertIn('Python not needed',result.stdout)

    def test_missing_lua_has_helpful_error_not_python_command_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            self._fixture(root)
            result=subprocess.run([shutil.which('make'), 'lua-prep'],cwd=root,env={'PATH':''},
                                  text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('py -3 setup_lua.py',result.stdout)
            self.assertNotIn('python: command not found',result.stdout)

    def test_checklist_matches_official_lua_prep(self):
        spec=importlib.util.spec_from_file_location('lua_prep',ROOT/'templates/setup_lua.py')
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mk=(ROOT/'templates/Makefile').read_text()
        expected=set('lua/'+n for n in module.FILES)
        names=set(re.search(r'^LUA_REQUIRED := (.+)$',mk,re.M).group(1).split())
        self.assertEqual(expected,names)

    def test_editor_uses_host_python_for_source_preparation(self):
        code=(ROOT/'novads/editor.py').read_text()
        self.assertIn("prep = [sys.executable, '-u', 'setup_lua.py']",code)
        self.assertIn("if prep_code != 0:",code)


if __name__=='__main__': unittest.main()
