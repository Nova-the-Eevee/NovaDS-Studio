"""Regression tests for Lua internal header prep (no network access required)."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent.parent
SCRIPT=HERE/'templates/setup_lua.py'
spec=importlib.util.spec_from_file_location('novads_setup_lua',SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class TestLuaPrep(unittest.TestCase):
    def test_internal_headers_listed(self):
        for hdr in ('lprefix.h','lapi.h','lobject.h','llimits.h','ljumptab.h','lstate.h','lgc.h','lvm.h','luaconf.h'):
            self.assertIn(hdr,mod.FILES)
        self.assertTrue(set(mod.CFILES).issubset({'lapi','lcode','lctype','ldebug','ldo','ldump','lfunc','lgc','llex','lmem','lobject','lopcodes','lparser','lstate','lstring','ltable','ltm','lundump','lvm','lzio','lauxlib','lbaselib','lcorolib','lmathlib','lstrlib','ltablib','lutf8lib'}))

    def test_prepare_repairs_legacy_partial_lua_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/'lua';folder.mkdir()
            (folder/'lapi.c').write_bytes(b'old')
            (folder/'lua.h').write_bytes(b'old')
            names=mod.FILES+['future_private.h']
            out=io.BytesIO()
            with tarfile.open(fileobj=out,mode='w:gz') as tar:
                for name in names:
                    data=('new '+name).encode()
                    info=tarfile.TarInfo('lua-'+mod.VERSION+'/src/'+name)
                    info.size=len(data)
                    tar.addfile(info,io.BytesIO(data))
                info=tarfile.TarInfo('lua-'+mod.VERSION+'/README')
                data=b'upstream';info.size=len(data)
                tar.addfile(info,io.BytesIO(data))
            tarpath=root/('lua-'+mod.VERSION+'.tar.gz')
            tarpath.write_bytes(out.getvalue())
            digest=hashlib.sha256(out.getvalue()).hexdigest()
            with patch.object(mod,'SHA256',digest):
                result=mod.prepare(root)
                self.assertEqual(result,folder)
                self.assertEqual((folder/'lprefix.h').read_bytes(),b'new lprefix.h')
                self.assertEqual((folder/'ljumptab.h').read_bytes(),b'new ljumptab.h')
                self.assertEqual((folder/'future_private.h').read_bytes(),b'new future_private.h')
                self.assertEqual((folder/'lapi.c').read_bytes(),b'new lapi.c')
                tarpath.unlink()
                self.assertEqual(mod.prepare(root),folder)

    def test_makefile_sources_match_lua_downloader(self):
        import re
        expected = {name + '.c' for name in mod.CFILES}
        for path in ('templates/Makefile','example_export/Makefile','example_export_2d2d/Makefile'):
            text = (HERE/path).read_text()
            match = re.search(r'^LUA_CFILES := (.+)$', text, re.M)
            self.assertIsNotNone(match)
            self.assertEqual(set(match.group(1).split()), expected)

    def test_generated_exports_have_fixed_prep(self):
        for path in ('example_export','example_export_2d2d'):
            self.assertEqual((HERE/path/'setup_lua.py').read_bytes(),SCRIPT.read_bytes())
            self.assertEqual((HERE/path/'source/main.c').read_bytes(),(HERE/'templates/main.c').read_bytes())
