# Installers and code signing

None of these scripts could be run in the environment where VibeSimulation was written (it only has Linux), so the Windows and macOS
installers are **untested**. They are short, standard recipes; expect to fix small path problems the first time.

## Windows (setup .exe with Inno Setup)
1. Install Python 3.9+ (with Tk) and [Inno Setup 6](https://jrsoftware.org/isdl.php).
2. Run `packaging\windows\build_installer.bat`. It builds the app with PyInstaller (`packaging\build.py`) and then
   `dist\VibeSimulation-<version>-windows-setup.exe`.
3. **Signing** (without it Windows SmartScreen warns "unknown publisher"): get a code-signing certificate (an EV certificate removes the
   warning at once; a normal one builds reputation over time). Sign the setup with
   `signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f cert.pfx /p PASSWORD dist\VibeSimulation-<version>-windows-setup.exe`
   or let Inno Setup do it (see the comments in `VibeSimulation.iss`). Also sign `VibeSimulation.exe` before packaging if you can.
4. An `.msi` is not produced; if a company needs one, wrap the setup with WiX or use `msiexec`-style deployment tools. The setup also supports
   silent install: `setup.exe /VERYSILENT /SUPPRESSMSGBOXES`.

## macOS (.dmg)
1. On a Mac run `packaging/macos/build_dmg.sh` (needs Python with Tk and the Xcode command line tools).
2. **Signing and notarization** (without them Gatekeeper refuses to open the app on other Macs): join the Apple Developer Program, create a
   "Developer ID Application" certificate, then
   `SIGN_ID="Developer ID Application: Your Name (TEAMID)" NOTARY_PROFILE=myprofile packaging/macos/build_dmg.sh`.
   The script signs with the hardened runtime and `packaging/macos/entitlements.plist`, submits to Apple's notary service and staples the ticket.
3. The python.org installer of Python ships a recent Tk; the Tk that comes with macOS itself is old and can look wrong.

## Linux
`python packaging/build.py` gives `dist/VibeSimulation-linux.tar.gz`. `packaging/linux/VibeSimulation.desktop` is a menu entry to copy to
`~/.local/share/applications/` (edit `Exec=` to the full path of the program).

## Version number
Change `__version__` in `src/vibesimulation/__init__.py` and `version` in `pyproject.toml` together. The About box, the installer names and the
update check all read it. Update checks stay off until `check_updates` is true and `update_url` is set in `~/.vibesimulation.json`.
