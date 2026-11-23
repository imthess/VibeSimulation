"""Per-OS display setup: crisp text on Windows (DPI awareness), sensible scaling everywhere."""
import os
import sys


def prepare():
    """Call BEFORE tk.Tk(). On Windows, opt in to per-monitor DPI so the OS does not bitmap-stretch (blur) the window."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)        # per-monitor
        except Exception:
            try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception: ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def ui_scale(root):
    """Pixel-size multiplier relative to the classic 96 dpi (1.0 .. 3.0). VIBE_UI_SCALE overrides."""
    try:
        v = float(os.environ.get("VIBE_UI_SCALE", ""))
        if v > 0: return max(0.75, min(3.0, v))
    except ValueError:
        pass
    try:
        return max(1.0, min(3.0, root.winfo_fpixels("1i") / 96.0 if sys.platform == "win32" else 1.0 if root.winfo_fpixels("1i") < 110 else root.winfo_fpixels("1i") / 96.0))
    except Exception:
        return 1.0


def setup(root):
    """After tk.Tk(): make Tk's point->pixel factor match the chosen scale; returns it."""
    s = ui_scale(root)
    try:
        if os.environ.get("VIBE_UI_SCALE"): root.tk.call("tk", "scaling", s * 96 / 72)
    except Exception:
        pass
    return s


def fit_geometry(root, want, scale=1.0):
    """Default window size scaled for DPI and clamped to the screen."""
    try:
        w, h = (int(x) for x in want.split("+")[0].split("x"))
    except Exception:
        w, h = 1360, 860
    w, h = round(w * scale), round(h * scale)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    return f"{min(w, int(sw * .94))}x{min(h, int(sh * .9))}"
