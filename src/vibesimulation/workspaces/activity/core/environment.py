"""Facts about this computer and the program's settings, for the Activity page and its reports. Never includes API keys."""
import platform
import sys
import tkinter

from vibesimulation import __version__

AI_KEYS = ("provider", "models", "bases", "model_manual", "import_target", "import_mode", "ai_button", "ai_sep_on", "ai_sep")


def system_info():
    """[(name, value)] about Python, the system and the optional packages."""
    rows = [("VibeSimulation", __version__), ("Python", sys.version.split()[0]), ("System", f"{platform.system()} {platform.release()} ({platform.machine()})"),
            ("Tk", str(tkinter.TkVersion))]
    for mod in ("PIL", "keyring"):
        try: m = __import__(mod); rows.append((mod, getattr(m, "__version__", None) or getattr(m, "version", "installed") or "installed"))
        except Exception: rows.append((mod, "not installed"))
    return [(k, str(v)) for k, v in rows]


def ai_settings(cfg):
    """[(name, value)] of every setting that changes what is sent to the AI and how (keys are not part of the settings file)."""
    rows = [(k, cfg[k]) for k in AI_KEYS if k in cfg]
    rows += sorted((k, v) for k, v in cfg.items() if k.startswith(("scan_", "ai_")) and k not in AI_KEYS and k != "ai_usage")
    return [(k, str(v)) for k, v in rows]
