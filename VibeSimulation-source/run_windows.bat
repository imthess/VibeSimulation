@echo off
rem Starts VibeSimulation from source. Needs Python 3.9+ (with tcl/tk) installed.
cd /d "%~dp0"
where py >nul 2>nul || (echo Python is not installed. Get it from https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .venv ( py -3 -m venv .venv )
call .venv\Scripts\activate.bat
python -m pip install --quiet pillow pyinstaller
set PYTHONPATH=%~dp0src
python packaging\run_app.py
