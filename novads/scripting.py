"""Real Lua 5.4 script syntax checks (no Lua reimplementation)."""
from __future__ import annotations
import ctypes
import ctypes.util
import shutil
import subprocess

class ScriptError(ValueError): pass


def validate_script(code: str) -> str:
    """Syntax-check via real installed Lua, or defer to DS runtime if absent.

    Does not execute the script. There is deliberately no fake subset parser.
    """
    if not isinstance(code,str):raise ScriptError('Script must be UTF-8 text')
    data=code.encode('utf-8')
    if b'\0' in data:raise ScriptError('Lua scripts cannot contain NUL bytes')
    if len(data)>24576:raise ScriptError('Maximum script size is 24 KiB on DS')
    # Installed Lua executables use their native parser for syntax checking.
    for exe in ('luac5.4','luac','lua5.4','lua'):
        binary=shutil.which(exe)
        if not binary: continue
        if 'luac' in exe:
            args=[binary,'-p','-']
        else:
            args=[binary,'-e','local s=io.read("*a");local f,e=load(s,"@script","t");if not f then io.stderr:write(e);os.exit(1) end']
        try:
            r=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
            if r.returncode:raise ScriptError(r.stderr.decode('utf-8','replace').strip() or 'Lua syntax error')
            return 'Lua parser: syntax OK'
        except (OSError,subprocess.TimeoutExpired):pass
    # ctypes is a fallback for systems with a native Lua library but no CLI.
    name=ctypes.util.find_library('lua5.4')
    if name:
        try:
            lib=ctypes.CDLL(name)
            lib.luaL_newstate.restype=ctypes.c_void_p
            lib.lua_close.argtypes=[ctypes.c_void_p]
            lib.luaL_loadbufferx.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_char_p]
            lib.luaL_loadbufferx.restype=ctypes.c_int
            lib.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p]
            lib.lua_tolstring.restype=ctypes.c_char_p
            state=lib.luaL_newstate()
            if state:
                try:
                    rc=lib.luaL_loadbufferx(state,data,len(data),b'@script',b't')
                    if rc:
                        err=lib.lua_tolstring(state,-1,None)
                        raise ScriptError(err.decode('utf-8','replace') if err else 'Lua syntax error')
                    return 'Lua parser: syntax OK'
                finally:lib.lua_close(state)
        except OSError:pass
    return 'Lua syntax not checked locally (the DS VM checks it at runtime)'
