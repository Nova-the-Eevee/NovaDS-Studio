@echo off
cd /d "%~dp0"
where py >NUL 2>NUL
if %errorlevel%==0 (py -3 run_editor.py) else (python run_editor.py)
if errorlevel 1 pause
