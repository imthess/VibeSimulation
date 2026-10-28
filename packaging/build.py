"""Build a stand-alone app for the current OS:  python packaging/build.py
Output: dist/VibeSimulation (folder / .app) and a zip/tar named for your OS."""
import platform, shutil, subprocess, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
try:
    import PIL, PyInstaller  # noqa
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow", "pyinstaller"])
subprocess.check_call([sys.executable, str(root / "packaging" / "make_icons.py")])
osname = platform.system()
icon = {"Windows": "icon.ico", "Darwin": "icon.icns"}.get(osname, "icon.png")
sys.path.insert(0, str(root / "src"))
import pkgutil, vibesimulation
hidden = []
for m in pkgutil.walk_packages(vibesimulation.__path__, "vibesimulation."):
    hidden += ["--hidden-import", m.name]
args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "VibeSimulation",
        "--paths", str(root / "src"), "--hidden-import", "PIL.ImageTk", "--hidden-import", "PIL.ImageGrab",
        *hidden, "--distpath", str(root / "dist"), "--workpath", str(root / "build"),
        "--specpath", str(root / "build"), "--icon", str(root / "packaging" / icon), str(root / "packaging" / "run_app.py")]
subprocess.check_call(args)
out = root / "dist"
tag = {"Windows": "windows", "Darwin": "macos"}.get(osname, "linux")
src = out / ("VibeSimulation.app" if osname == "Darwin" else "VibeSimulation")
if osname == "Darwin": shutil.make_archive(str(out / f"VibeSimulation-{tag}"), "zip", out, "VibeSimulation.app")
else: shutil.make_archive(str(out / f"VibeSimulation-{tag}"), "zip" if osname == "Windows" else "gztar", out, "VibeSimulation")
print("Built", src)
