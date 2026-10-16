#!/usr/bin/env python3
"""Prepare the official Lua 5.4.9 source once for a NovaDS DS build.

Run: python setup_lua.py
Offline: put the official lua-5.4.9.tar.gz in this project's directory.
This script pins Lua source SHA-256 and extracts all required Lua core headers and selected C source files.
"""
from pathlib import Path
import hashlib
import io
import sys
import tarfile
import urllib.request

VERSION = '5.4.9'
URL = 'https://www.lua.org/ftp/lua-5.4.9.tar.gz'
SHA256 = '2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6'
# Build only Lua core and selected libraries, not Lua executable or OS libraries.
CFILES = "lapi lcode lctype ldebug ldo ldump lfunc lgc llex lmem lobject          lopcodes lparser lstate lstring ltable ltm lundump lvm lzio lauxlib          lbaselib lcorolib lmathlib lstrlib ltablib lutf8lib".split()

# All public and internal headers required by Lua 5.4.9.
HEADERS = "lua.h lauxlib.h lualib.h luaconf.h lua.hpp            lapi.h lcode.h lctype.h ldebug.h ldo.h lfunc.h lgc.h ljumptab.h            llex.h llimits.h lmem.h lobject.h lopcodes.h lopnames.h            lparser.h lprefix.h lstate.h lstring.h ltable.h ltm.h            lundump.h lvm.h lzio.h".split()
FILES = [name + '.c' for name in CFILES] + HEADERS



def prepare(dest=None, archive=None):
    root = Path(dest or Path(__file__).resolve().parent)
    target = root / 'lua'
    # Also detects upgrades of older, *incomplete* lua/ directories.
    if all((target / name).is_file() for name in FILES):
        return target
    archive = Path(archive) if archive else root / ('lua-' + VERSION + '.tar.gz')
    downloaded = not archive.is_file()
    if downloaded:
        print('Downloading official Lua ' + VERSION + ' from ' + URL, flush=True)
        try:
            with urllib.request.urlopen(URL, timeout=30) as handle:
                contents = handle.read(2_000_000)
        except Exception as e:
            raise RuntimeError('Missing Lua internal headers (possibly from an older NovaDS export). '
                               'Could not download the source archive. Download ' + URL +
                               ' in your browser, put the tar.gz beside setup_lua.py, '
                               'then run make again. ' + str(e)) from e
    else:
        contents = archive.read_bytes()
    digest = hashlib.sha256(contents).hexdigest()
    if digest != SHA256:
        raise RuntimeError('Lua source SHA-256 mismatch: ' + digest +
                           ' (expected ' + SHA256 + ')')

    prefix = 'lua-' + VERSION + '/src/'
    with tarfile.open(fileobj=io.BytesIO(contents), mode='r:gz') as tar:
        members = {member.name: member for member in tar.getmembers()}
        missing = [name for name in FILES if prefix + name not in members]
        if missing:
            raise RuntimeError('Lua archive is missing expected source files: ' +
                               ', '.join(missing))
        # Always unpack all private Lua headers, even if upstream adds one.
        extra_headers = [member.name[len(prefix):] for member in members.values()
                         if member.name.startswith(prefix) and
                         member.name.endswith('.h') and '/' not in member.name[len(prefix):]]
        names = sorted(set(FILES + extra_headers))
        target.mkdir(exist_ok=True, parents=True)
        for name in names:
            member = members[prefix + name]
            stream = tar.extractfile(member)
            if stream is None:
                raise RuntimeError('Could not extract Lua source file: ' + name)
            (target / name).write_bytes(stream.read())
        readme = tar.extractfile('lua-' + VERSION + '/README')
        if readme:
            (target / 'LUA_UPSTREAM_README').write_bytes(readme.read())

    # Keep the verified source archive for reproducible/offline re-exports.
    if downloaded:
        archive.write_bytes(contents)
    print('Lua ' + VERSION + ' source ready (' + str(len(names)) +
          ' source/header files; ' + str(len(HEADERS)) + ' required headers).', flush=True)
    return target


if __name__=='__main__':
    try:
        prepare()
    except Exception as exc:
        print('ERROR:',exc,file=sys.stderr)
        raise SystemExit(1)
