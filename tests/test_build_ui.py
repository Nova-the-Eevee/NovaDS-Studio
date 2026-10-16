"""Standalone checks for the v0.4.3 build launcher and compact-window log UI."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from novads.editor import Editor

class LauncherTests(unittest.TestCase):
    def test_msys_windows_path(self):
        self.assertEqual(Editor._msys_path(Path('C:/Users/Test/Desktop')), '/c/Users/Test/Desktop') if os.name == 'nt' else self.assertTrue(Editor._msys_path(Path('.')).startswith('/'))

    def test_non_windows_requires_make_and_devkitarm(self):
        if os.name == 'nt':
            self.skipTest('Linux/macOS branch only')
        obj = object.__new__(Editor)
        obj.export_path = Path('/tmp/novads-test')
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'DEVKITARM'):
                obj._build_command()
        with patch.dict(os.environ, {'DEVKITARM':'/opt/devkitpro/devkitARM'}):
            if __import__('shutil').which('make'):
                self.assertIn('--no-print-directory', obj._build_command())

    def test_log_window_no_truncation_and_clipboard(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception as exc:
            self.skipTest(f'No X display: {exc}')
        root.withdraw()
        ed = Editor(root)
        win = ed.show_build_output()
        data = 'Hello compile!\n' + ('X' * 60000) + '\nERROR at main.c:10\n'
        ed._append_build_output(data)
        self.assertEqual(''.join(ed.build_log_content), data)
        self.assertEqual(ed.build_log_text.get('1.0','end-1c'), data)
        ed._copy_build_log()
        self.assertEqual(root.clipboard_get(), data)
        ed._clear_build_log()
        self.assertEqual(''.join(ed.build_log_content), '')
        ed.build_log_window.destroy()
        root.destroy()

if __name__ == '__main__': unittest.main()

class BuildExecutionTests(unittest.TestCase):
    def test_success_and_failure_stream_output(self):
        import tempfile
        import sys
        import time
        from unittest.mock import patch
        import tkinter as tk
        try:
            root = tk.Tk()
        except Exception as exc:
            self.skipTest(f'No display: {exc}')
        root.withdraw()
        ed = Editor(root)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            ed.export_path = folder
            # The editor now prepares Lua via its own Python interpreter before
            # launching the MSYS2/devkitPro command. Simulate the preparation
            # step so this UI test does not require downloading the Lua archive.
            (folder / 'setup_lua.py').write_text(
                'print("Lua source prepared by host Python", flush=True)\n', encoding='utf-8')
            build_script = folder / 'mock_build.py'
            # Test both status paths, and stderr merging into the output window.
            for ok in (True, False):
                build_script.write_text(
                    'import sys, pathlib\n'
                    'print("building main.c", flush=True)\n'
                    'sys.stderr.write("compiler-warning: original source location\\n")\n'
                    'print("building scene.c", flush=True)\n'
                    + ('pathlib.Path("NovaDS_Game.nds").write_bytes(b"NDS")\n'
                       if ok else 'print("fatal error: missing include!", flush=True)\n')
                    + f'sys.exit({0 if ok else 2})\n', encoding='utf-8')
                if not ok:
                    (folder / 'NovaDS_Game.nds').unlink(missing_ok=True)
                with patch('novads.editor.export_to'), patch.object(ed, '_build_command', return_value=[sys.executable, str(build_script)]), patch('novads.editor.messagebox.showinfo'), patch('novads.editor.messagebox.showerror') as err:
                    ed.build()
                    deadline = time.monotonic() + 8
                    while ed.build_running and time.monotonic() < deadline:
                        root.update()
                        time.sleep(.02)
                    root.update()
                    self.assertFalse(ed.build_running, 'build did not finish')
                    output = ''.join(ed.build_log_content)
                    self.assertIn('Lua source prepared by host Python', output)
                    self.assertIn('Lua preparation complete.', output)
                    self.assertIn('building main.c', output)
                    self.assertIn('compiler-warning: original source location', output)
                    if ok:
                        self.assertIn('SUCCESS:', output)
                        self.assertFalse(err.called)
                    else:
                        self.assertIn('fatal error: missing include!', output)
                        self.assertIn('FAILED:', output)
                        self.assertTrue(err.called)
        root.destroy()
