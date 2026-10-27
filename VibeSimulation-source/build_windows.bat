@echo off
rem Builds dist\VibeSimulation\VibeSimulation.exe (a folder you can copy anywhere).
cd /d "%~dp0"
where py >nul 2>nul || (echo Python is not installed. Get it from https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .venv ( py -3 -m venv .venv )
call .venv\Scripts\activate.bat
python -m pip install --quiet pillow pyinstaller
python packaging\build.py
echo.
echo Done. Run dist\VibeSimulation\VibeSimulation.exe
pause
