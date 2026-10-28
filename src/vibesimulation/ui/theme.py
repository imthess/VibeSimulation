"""Colours, fonts and ttk styles (light and dark)."""
import tkinter as tk
from tkinter import font as tkfont, ttk

from .shapes import mix, on_color

ACCENTS = {  # name: (accent in light mode, accent in dark mode)
    "Graphite": ("#1b2234", "#e6e9f0"), "Blue": ("#2f5bea", "#7ba3ff"), "Teal": ("#0f8a80", "#3dd6c6"), "Green": ("#1f9d55", "#5fdc8c"),
    "Amber": ("#c9780a", "#f2b84b"), "Rose": ("#d63a5a", "#ff7f98"), "Violet": ("#6d4fe0", "#a99bff"), "Indigo": ("#4f46e5", "#8b93ff"),
}
DEFAULT_ACCENT = "Blue"
RADII = {"Sharp": (4, 4), "Rounded": (20, 11), "Pill": (26, 99)}     # (cards, buttons)
DENSITY = {"Compact": 0.8, "Comfortable": 1.0, "Spacious": 1.25}
SCALES = (85, 100, 115, 130, 150)

# Soft, calm surfaces: a tinted backdrop, lighter panels floating on it, one dark rail.
_LIGHT = dict(bg="#e5ebf1", card="#f7f9fb", border="#d9e1e9", text="#111827", muted="#6b7585", soft="#ecf0f5", soft_h="#dfe6ee", field="#edf1f6",
              ok="#157f3b", okbg="#e3f3ea", bad="#b42318", badbg="#fbe9e7", canvas="#fbfcfd", dot="#d3dce5", on="#16a34a", off="#a3abbd",
              pin="#2f3650", gatefill="#ffffff", rail="#1b1e27", rail_sel="#353a47", rail_fg="#aab1c0", rail_on="#ffffff")
_DARK = dict(bg="#131417", card="#1c1e23", border="#2a2d34", text="#eceef3", muted="#8b919d", soft="#25282f", soft_h="#2f333b", field="#181a1f",
             ok="#4ade80", okbg="#14261c", bad="#f87171", badbg="#2a1719", canvas="#17181c", dot="#272a31", on="#34d399", off="#4a5368",
             pin="#a9b2c8", gatefill="#1d2230", rail="#0c0d0f", rail_sel="#2b2e36", rail_fg="#8d93a1", rail_on="#ffffff")


def palette(dark, accent, high_contrast=False):
    P = dict(_DARK if dark else _LIGHT)
    if high_contrast:
        P["text"] = "#ffffff" if dark else "#000000"; P["muted"] = mix(P["text"], P["card"], 0.22)
        P["border"] = mix(P["text"], P["card"], 0.5); P["soft_h"] = mix(P["text"], P["card"], 0.18)
    a = accent
    P["accent"] = a; P["accent_h"] = mix(a, "#ffffff" if dark else "#000000", 0.14); P["accent_fg"] = on_color(a)
    P["sel"] = mix(a, P["card"], 0.55 if dark else 0.86); P["infobg"] = mix(a, P["card"], 0.88 if not dark else 0.82); P["label"] = a
    P["shadow"] = mix(P["bg"], "#000000", 0.16 if dark else 0.09)
    return P


def system_dark():
    """True when the operating system is set to a dark appearance (False if it cannot be told)."""
    import subprocess, sys
    try:
        if sys.platform.startswith("win"):
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        if sys.platform == "darwin":
            return "dark" in subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True, timeout=2).stdout.lower()
        out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], capture_output=True, text=True, timeout=2).stdout.lower()
        if out.strip(): return "dark" in out
        out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"], capture_output=True, text=True, timeout=2).stdout.lower()
        return "dark" in out
    except Exception:
        return False


def pick_font(root, names, default):
    have = set(tkfont.families(root))
    return next((n for n in names if n in have), default)


def auto(sb, pack=None):
    """Scrollbar callback that hides the bar when everything fits."""
    def cb(lo, hi):
        need = float(lo) > 0 or float(hi) < 1
        if pack: (sb.pack(side="right", fill="y", before=pack) if need else sb.pack_forget())
        else: (sb.grid() if need else sb.grid_remove())
        sb.set(lo, hi)
    return cb


FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Inter", "Ubuntu", "Noto Sans", "Cantarell", "Helvetica Neue", "DejaVu Sans"]
MONOS = ["JetBrains Mono", "Cascadia Code", "SF Mono", "Consolas", "Ubuntu Mono", "DejaVu Sans Mono"]


class Theme:
    """Palette, fonts, shape and density settings. Everything that can change at run time lives here;
    widgets register a repaint callback in `themed` and are repainted by `apply()`."""
    def __init__(self, root, cfg):
        self.root, self.cfg, self.themed = root, cfg, []
        self.style = ttk.Style()
        try: self.style.theme_use("clam")
        except tk.TclError: pass
        self.f_body = tkfont.Font(root=root); self.f_bold = tkfont.Font(root=root, weight="bold"); self.f_small = tkfont.Font(root=root)
        self.f_title = tkfont.Font(root=root); self.f_mono = tkfont.Font(root=root); self.f_logo = tkfont.Font(root=root, weight="bold")
        self.f_icon = tkfont.Font(root=root, weight="bold"); self.f_big = tkfont.Font(root=root); self.f_glyph = tkfont.Font(root=root, weight="bold"); self.f_rail = tkfont.Font(root=root)
        self.sans = "TkDefaultFont"; self.dark = False; self.P = palette(False, ACCENTS[DEFAULT_ACCENT][0])
        self.kbd = False
        self.read_cfg()

    # ---- settings -> look
    def read_cfg(self):
        c = self.cfg
        mode = c.get("mode") or ("dark" if c.get("theme") == "dark" else "light" if c.get("theme") else "system")
        self.mode = mode if mode in ("light", "dark", "system") else "system"
        self.dark = system_dark() if self.mode == "system" else self.mode == "dark"
        acc = c.get("accent", DEFAULT_ACCENT)
        pair = ACCENTS.get(acc)
        base = (pair[1] if self.dark else pair[0]) if pair else (acc if isinstance(acc, str) and acc.startswith("#") and len(acc) == 7 else ACCENTS[DEFAULT_ACCENT][0])
        if not pair and self.dark: base = mix(base, "#ffffff", 0.18)
        self.P = palette(self.dark, base, bool(c.get("high_contrast")))
        self.r_card, rb = RADII.get(c.get("corners", "Rounded"), RADII["Rounded"]); self.r_btn = rb
        self.dens = DENSITY.get(c.get("density", "Comfortable"), 1.0)
        self.motion = not c.get("reduce_motion", False)
        scale = int(c.get("text_scale", 100)) / 100
        fam = c.get("font", "Auto"); have = set(tkfont.families(self.root))
        self.sans = fam if fam in have else pick_font(self.root, FAMILIES, "TkDefaultFont")
        mono = pick_font(self.root, MONOS, "TkFixedFont")
        for f, size in ((self.f_body, 10), (self.f_bold, 10), (self.f_small, 9), (self.f_title, 14), (self.f_logo, 15), (self.f_icon, 14), (self.f_big, 24), (self.f_glyph, 34), (self.f_rail, 19)):
            f.configure(family=self.sans, size=max(7, round(size * scale)))
        self.f_mono.configure(family=mono, size=max(8, round(11 * scale)))

    def dp(self, v): return max(0, round(v * self.dens))

    def mode_label(self): return {"light": "Light", "dark": "Dark", "system": "System"}[self.mode]

    def set_mode(self, mode):
        self.cfg["mode"] = mode; self.refresh()

    def toggle(self):
        self.set_mode("light" if self.dark else "dark")

    def refresh(self):
        self.read_cfg(); self.apply()

    def apply(self):
        P, st = self.P, self.style
        self.root.configure(bg=P["bg"])
        st.configure(".", background=P["card"], foreground=P["text"], font=self.f_body)
        for nm in ("Vertical", "Horizontal"):
            lay = f"Thin.{nm}.TScrollbar"
            st.layout(lay, [(f"{nm}.Scrollbar.trough", {"sticky": "nswe", "children": [(f"{nm}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
            st.configure(lay, troughcolor=P["card"], background=P["soft_h"], bordercolor=P["card"], lightcolor=P["soft_h"], darkcolor=P["soft_h"], gripcount=0,
                         width=9, arrowsize=9, relief="flat")
            st.map(lay, background=[("active", P["muted"]), ("pressed", P["muted"])])
        ent = dict(fieldbackground=P["field"], foreground=P["text"], background=P["field"], bordercolor=P["border"], lightcolor=P["field"],
                   darkcolor=P["field"], insertcolor=P["text"], padding=(8, 5), selectbackground=P["sel"], selectforeground=P["text"])
        st.configure("Modern.TEntry", **ent); st.map("Modern.TEntry", bordercolor=[("focus", P["accent"])], lightcolor=[("focus", P["accent"])], darkcolor=[("focus", P["accent"])])
        st.configure("Modern.TCombobox", **ent, arrowcolor=P["muted"], arrowsize=14)
        st.map("Modern.TCombobox", fieldbackground=[("readonly", P["field"])], foreground=[("readonly", P["text"])], bordercolor=[("focus", P["accent"])],
               lightcolor=[("focus", P["accent"])], darkcolor=[("focus", P["accent"])], background=[("active", P["soft"])], selectbackground=[("readonly", P["field"])],
               selectforeground=[("readonly", P["text"])])
        self.root.option_add("*TCombobox*Listbox.background", P["card"]); self.root.option_add("*TCombobox*Listbox.foreground", P["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", P["accent"]); self.root.option_add("*TCombobox*Listbox.selectForeground", P["accent_fg"])
        self.root.option_add("*TCombobox*Listbox.font", self.f_body)
        st.configure("Card.TRadiobutton", background=P["card"], foreground=P["text"], focuscolor=P["card"], indicatorbackground=P["field"], indicatorforeground=P["accent"])
        st.map("Card.TRadiobutton", background=[("active", P["card"])], indicatorbackground=[("selected", P["accent"])])
        for nm, bg in (("Card.TCheckbutton", P["card"]), ("Page.TCheckbutton", P["bg"])):
            st.configure(nm, background=bg, foreground=P["text"], focuscolor=bg, indicatorbackground=P["field"], indicatorforeground=P["accent"], bordercolor=P["border"])
            st.map(nm, background=[("active", bg)], indicatorbackground=[("selected", P["accent"])], foreground=[("active", P["text"])])
        st.configure("Modern.Treeview", background=P["card"], fieldbackground=P["card"], foreground=P["text"], rowheight=max(22, round(self.f_body.metrics("linespace") * 1.8 * self.dens + 4)), borderwidth=0, relief="flat",
                     lightcolor=P["card"], darkcolor=P["card"], bordercolor=P["card"])
        st.map("Modern.Treeview", background=[("selected", P["sel"])], foreground=[("selected", P["text"])])
        st.configure("Modern.Treeview.Heading", background=P["soft"], foreground=P["muted"], relief="flat", borderwidth=0, font=self.f_bold, padding=(6, 6),
                     lightcolor=P["soft"], darkcolor=P["soft"], bordercolor=P["soft"])
        st.map("Modern.Treeview.Heading", background=[("active", P["soft_h"])])
        st.layout("Modern.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        for _ in range(2):      # second pass: widgets that copy their parent's colour see the parent's new colour
            for fn in list(self.themed):
                try: fn()
                except tk.TclError:
                    if fn in self.themed: self.themed.remove(fn)
