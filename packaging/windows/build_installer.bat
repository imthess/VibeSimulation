@echo off
rem Builds dist\VibeSimulation-<version>-windows-setup.exe on Windows.
rem Needs: Python 3.9+ (with Tk), and Inno Setup 6 (https://jrsoftware.org/isdl.php) with iscc.exe on PATH or in its default folder.
cd /d "%~dp0\..\.."
python packaging\build.py || goto :fail
for /f %%v in ('python -c "import sys; sys.path.insert(0,'src'); import vibesimulation; print(vibesimulation.__version__)"') do set VER=%%v
set ISCC=iscc
where iscc >nul 2>nul || set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
%ISCC% packaging\windows\VibeSimulation.iss /DAppVersion=%VER% || goto :fail
echo.
echo Installer: dist\VibeSimulation-%VER%-windows-setup.exe
exit /b 0
:fail
echo Build failed.
exit /b 1
