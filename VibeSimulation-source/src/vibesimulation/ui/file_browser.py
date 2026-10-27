"""Files-style open / save dialog: places sidebar (Recent, Starred, Network, Trash, folders, drives), back / forward,
clickable path bar, search, list and icon views, sortable columns, stars, rename, new folder, move to Trash and restore,
properties and keyboard shortcuts - the same on Windows, macOS and Linux."""
import datetime
import os
import queue
import shutil
import string
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from urllib.parse import quote, unquote, urlparse

from .theme import auto
from .widgets import Btn

LINUX, MAC, WIN = sys.platform.startswith("linux"), sys.platform == "darwin", os.name == "nt"


# ------------------------------------------------------------------------------------------------ helpers
def fmt_size(n):
    if n < 1000: return f"{n} bytes"
    for u in ("kB", "MB", "GB", "TB"):
        n /= 1000
        if n < 1000 or u == "TB": return f"{n:.1f} {u}"


def fmt_time(ts):
    try: d = datetime.datetime.fromtimestamp(ts)
    except (OverflowError, OSError, ValueError): return ""
    today = datetime.date.today(); days = (today - d.date()).days; hm = d.strftime("%H:%M")
    if days == 0: return f"Today, {hm}"
    if days == 1: return f"Yesterday, {hm}"
    if 0 < days < 7: return d.strftime("%A, ") + hm
    if d.year == today.year: return d.strftime("%d %b, ") + hm
    return d.strftime("%d %b %Y")


def user_dirs():
    """Home plus the standard folders (from XDG user-dirs when present)."""
    home = Path.home(); found = {}
    cfg = home / ".config" / "user-dirs.dirs"
    try:
        for line in cfg.read_text().splitlines():
            if line.startswith("XDG_") and "=" in line:
                k, v = line.split("=", 1); found[k.replace("XDG_", "").replace("_DIR", "").title()] = Path(os.path.expandvars(v.strip().strip('"')))
    except OSError: pass
    out = [("Home", home)]
    for name in ("Documents", "Music", "Pictures", "Videos", "Downloads"):
        p = found.get(name) or home / name
        if p.is_dir(): out.append((name, p))
    return out


def volumes():
    out = []
    if WIN:
        out = [(f"{d}:", Path(f"{d}:\\")) for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
    elif MAC:
        out = [(p.name, p) for p in sorted(Path("/Volumes").glob("*")) if p.is_dir()]
    else:
        user = os.environ.get("USER") or os.path.basename(str(Path.home()))
        for base in (Path("/media") / user, Path("/run/media") / user, Path("/mnt")):
            try: out += [(p.name, p) for p in sorted(base.iterdir()) if p.is_dir()]
            except OSError: pass
    return out


def network_places():
    if LINUX:
        try:
            g = Path(f"/run/user/{os.getuid()}/gvfs")
            return [(p.name, p) for p in sorted(g.iterdir())]
        except OSError: return []
    if MAC:
        try: return [(p.name, p) for p in sorted(Path("/Volumes").iterdir()) if p.is_mount() and not p.samefile("/")]
        except OSError: return []
    return []


def trash_dir():
    if LINUX: return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "Trash"
    if MAC: return Path.home() / ".Trash"
    return None


def _unique(dest):
    n, base = 2, dest
    while dest.exists() or dest.is_symlink():
        dest = base.with_name(f"{base.stem}.{n}{base.suffix}"); n += 1
    return dest


def trash_move(path):
    """Move to the system Trash. Raises OSError on failure."""
    p = Path(path)
    if LINUX:
        base = trash_dir(); files, info = base / "files", base / "info"; files.mkdir(parents=True, exist_ok=True); info.mkdir(parents=True, exist_ok=True)
        dest = files / p.name; n = 2
        while dest.exists() or dest.is_symlink() or (info / (dest.name + ".trashinfo")).exists():
            dest = files / f"{p.stem}.{n}{p.suffix}"; n += 1
        (info / (dest.name + ".trashinfo")).write_text("[Trash Info]\nPath=" + quote(str(p.absolute())) + "\nDeletionDate=" + time.strftime("%Y-%m-%dT%H:%M:%S") + "\n")
        shutil.move(str(p), str(dest))
    elif MAC:
        shutil.move(str(p), str(_unique(trash_dir() / p.name)))
    else:
        import ctypes
        from ctypes import wintypes
        class OP(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort),
                        ("fAnyOperationsAborted", wintypes.BOOL), ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
        op = OP(None, 3, str(p.absolute()) + "\0", None, 0x40 | 0x10 | 0x4, False, None, None)
        if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) != 0: raise OSError("Windows could not move it to the Recycle Bin")


@dataclass
class Entry:
    name: str
    path: Path
    is_dir: bool
    size: int = 0
    mtime: float = 0.0
    where: str = ""          # folder shown in the Location column (Recent, Starred, Search, Trash)
    info: str = ""           # Trash: the .trashinfo file


def entry_of(p, where="", count=True):
    try: st = p.stat()
    except OSError: return None
    d = p.is_dir(); size = st.st_size
    if d and count:
        try: size = len(os.listdir(p))
        except OSError: size = 0
    return Entry(p.name or str(p), p, d, size, st.st_mtime, where)


# ------------------------------------------------------------------------------------------------ the dialog
class FileDialog(tk.Toplevel):
    def __init__(self, ctx, mode, title, exts, start=None, name=""):
        super().__init__(ctx.root)
        self.ctx, self.mode, self.exts, self.result = ctx, mode, [e.lower() for e in exts], None
        P = ctx.P; self.P = P; self.cfg = ctx.cfg
        self.title(title); self.transient(ctx.root); self.configure(bg=P["bg"]); self.geometry("980x640"); self.minsize(760, 460)
        home = Path.home()
        first = Path(start) if start and Path(start).is_dir() else home
        self.hist, self.hi = [], -1
        self.loc = ("dir", first); self.entries, self.sel = [], None
        self.sort_key, self.sort_asc = "name", True
        self.show_hidden = tk.BooleanVar(value=bool(self.cfg.get("fd_hidden", False)))
        self.view = tk.StringVar(value=self.cfg.get("fd_view", "list"))
        self.filter = tk.StringVar(); self.q = queue.Queue(); self.search_gen = 0; self.typed, self.typed_t = "", 0.0
        self.icons = {}
        self._build(name)
        self.goto(("dir", first))
        self.update_idletasks()
        try: self.grab_set()
        except tk.TclError: pass
        r = ctx.root; self.geometry(f"+{r.winfo_rootx() + max(0, (r.winfo_width() - 980) // 2)}+{r.winfo_rooty() + max(0, (r.winfo_height() - 640) // 4)}")
        self.after(120, self._poll)

    # ------------------------------------------------------------------ construction
    def _build(self, name):
        ctx, P = self.ctx, self.P
        mk = lambda w: w.configure(bg=P["bg"])
        top = tk.Frame(self, bg=P["bg"]); top.pack(fill="x", padx=12, pady=(12, 6))
        self.b_back = Btn(ctx, top, "‹", self.back, "ghost", padx=10, pady=2, font=ctx.f_icon).tip("Back (Alt+←)"); self.b_back.pack(side="left")
        self.b_fwd = Btn(ctx, top, "›", self.forward, "ghost", padx=10, pady=2, font=ctx.f_icon).tip("Forward (Alt+→)"); self.b_fwd.pack(side="left", padx=(0, 6))
        self.bar = tk.Frame(top, bg=P["card"], highlightthickness=1, highlightbackground=P["border"]); self.bar.pack(side="left", fill="x", expand=True, ipady=2)
        self.bar.bind("<Button-1>", lambda e: self.edit_path())
        Btn(ctx, top, "☰", self.main_menu, "ghost", padx=10, pady=2, font=ctx.f_icon).tip("Menu").pack(side="right", padx=(6, 0))
        self.b_view = Btn(ctx, top, "▦", self.toggle_view, "ghost", padx=10, pady=2, font=ctx.f_icon).tip("Switch between list and icon view"); self.b_view.pack(side="right")
        Btn(ctx, top, "⌕", self.toggle_search, "ghost", padx=10, pady=2, font=ctx.f_icon).tip("Search (Ctrl+F)").pack(side="right", padx=(6, 0))
        self.search_row = tk.Frame(self, bg=P["bg"]); self.search = tk.StringVar()
        self.search_ent = ttk.Entry(self.search_row, textvariable=self.search, style="Modern.TEntry"); self.search_ent.pack(fill="x", padx=12, ipady=3)
        self.search.trace_add("write", lambda *a: self._search_later())
        self.search_ent.bind("<Escape>", lambda e: (self.toggle_search(), "break")[1])
        mid = tk.Frame(self, bg=P["bg"]); mid.pack(fill="both", expand=True, padx=12)
        self.side = tk.Frame(mid, bg=P["soft"], width=190, highlightthickness=1, highlightbackground=P["border"]); self.side.pack(side="left", fill="y", padx=(0, 8)); self.side.pack_propagate(False)
        self.side_items = []
        self._sidebar()
        self.main = tk.Frame(mid, bg=P["card"], highlightthickness=1, highlightbackground=P["border"]); self.main.pack(side="left", fill="both", expand=True)
        self._list(); self._grid()
        bot = tk.Frame(self, bg=P["bg"]); bot.pack(fill="x", padx=12, pady=(8, 12))
        self.status = tk.Label(bot, text="", bg=P["bg"], fg=P["muted"], font=ctx.f_small, anchor="w"); self.status.pack(fill="x", pady=(0, 6))
        row = tk.Frame(bot, bg=P["bg"]); row.pack(fill="x")
        tk.Label(row, text="Name" if self.mode == "save" else "Selected", bg=P["bg"], fg=P["muted"], font=ctx.f_small).pack(side="left", padx=(0, 8))
        self.name = tk.StringVar(value=name); self.entry = ttk.Entry(row, textvariable=self.name, style="Modern.TEntry"); self.entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.entry.bind("<Return>", lambda e: self.accept())
        opts = ["All files"]
        if self.exts: opts.insert(0, "Supported (" + ", ".join(self.exts) + ")")
        self.filter.set(opts[0]); fcb = ttk.Combobox(row, textvariable=self.filter, values=opts, state="readonly", style="Modern.TCombobox", width=22)
        fcb.pack(side="left", padx=8); fcb.bind("<<ComboboxSelected>>", lambda e: self.fill())
        Btn(ctx, row, "Save" if self.mode == "save" else "Open", self.accept, "primary").pack(side="right", padx=(8, 0))
        Btn(ctx, row, "Cancel", self.destroy, "secondary").pack(side="right")
        self._keys()

    def _icon(self, kind):
        if kind in self.icons: return self.icons[kind]
        im = tk.PhotoImage(width=18, height=16)
        if kind == "dir":
            im.put("#3584e4", to=(0, 2, 8, 5)); im.put("#62a0ea", to=(0, 4, 18, 15)); im.put("#3584e4", to=(0, 7, 18, 8))
        else:
            im.put("#9a9996", to=(3, 0, 15, 16)); im.put("#f6f5f4", to=(4, 1, 14, 15)); im.put("#c0bfbc", to=(6, 5, 12, 6)); im.put("#c0bfbc", to=(6, 8, 12, 9)); im.put("#c0bfbc", to=(6, 11, 12, 12))
        self.icons[kind] = im
        return im

    def _sidebar(self):
        P, ctx = self.P, self.ctx
        for w in self.side.winfo_children(): w.destroy()
        self.side_items = []
        def item(label, loc, glyph):
            l = tk.Label(self.side, text=f" {glyph}  {label}", bg=P["soft"], fg=P["text"], font=ctx.f_body, anchor="w", cursor="hand2", padx=8, pady=5)
            l.pack(fill="x", padx=6, pady=1); l.bind("<Button-1>", lambda e, loc=loc: self.goto(loc)); self.side_items.append((l, loc))
            l.bind("<Button-3>", lambda e, loc=loc: self.side_menu(e, loc))
        for label, loc, g in (("Recent", ("recent",), "◷"), ("Starred", ("starred",), "★"), ("Network", ("network",), "⌁"), ("Trash", ("trash",), "♻")): item(label, loc, g)
        tk.Frame(self.side, bg=P["border"], height=1).pack(fill="x", padx=10, pady=6)
        for label, p in user_dirs(): item(label, ("dir", p), "⌂" if label == "Home" else "▤")
        vols = volumes()
        if vols or not WIN:
            tk.Frame(self.side, bg=P["border"], height=1).pack(fill="x", padx=10, pady=6)
            if not WIN: item("Computer", ("dir", Path(Path.home().anchor or "/")), "▣")
            for label, p in vols: item(label, ("dir", p), "⏏" if not WIN else "▣")
        self._side_mark()

    def _side_mark(self):
        P = self.P
        for l, loc in self.side_items:
            on = loc == self.loc or (loc[0] == "dir" and self.loc[0] == "dir" and loc[1] == self.loc[1])
            l.configure(bg=P["accent"] if on else P["soft"], fg=P["accent_fg"] if on else P["text"])

    def _list(self):
        P, ctx = self.P, self.ctx
        self.list_box = tk.Frame(self.main, bg=P["card"])
        cols = ("size", "mod", "where", "star")
        self.tree = ttk.Treeview(self.list_box, columns=cols, selectmode="browse", style="Modern.Treeview")
        self.tree.column("#0", width=330, stretch=True); self.tree.column("size", width=100, anchor="e", stretch=False)
        self.tree.column("mod", width=150, anchor="w", stretch=False); self.tree.column("where", width=0, stretch=False); self.tree.column("star", width=36, anchor="center", stretch=False)
        for c, t in (("size", "Size"), ("mod", "Modified"), ("where", "Location"), ("star", "★")): self.tree.heading(c, text=t, command=(lambda c=c: self.sort_by({"size": "size", "mod": "mod", "where": "where"}.get(c))) if c != "star" else "")
        self.tree.heading("#0", text="Name", anchor="w", command=lambda: self.sort_by("name"))
        sb = ttk.Scrollbar(self.list_box, command=self.tree.yview, style="Thin.Vertical.TScrollbar"); self.tree.configure(yscrollcommand=auto(sb, self.tree))
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("dim", foreground=P["muted"])
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select); self.tree.bind("<Double-1>", self.on_double)
        self.tree.bind("<Button-1>", self.on_tree_click, add="+"); self.tree.bind("<Button-3>", self.on_right); self.tree.bind("<Button-2>", self.on_right)

    def _grid(self):
        P = self.P
        self.grid_box = tk.Frame(self.main, bg=P["card"])
        self.cv = tk.Canvas(self.grid_box, bg=P["card"], highlightthickness=0); sb = ttk.Scrollbar(self.grid_box, command=self.cv.yview, style="Thin.Vertical.TScrollbar")
        self.cv.configure(yscrollcommand=auto(sb, self.cv)); self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.draw_grid()); self.cv.bind("<Button-1>", self.on_cv_click); self.cv.bind("<Double-1>", self.on_cv_double)
        self.cv.bind("<Button-3>", self.on_cv_right); self.cv.bind("<Button-2>", self.on_cv_right)
        for ev, d in (("<Button-4>", -1), ("<Button-5>", 1)): self.cv.bind(ev, lambda e, d=d: self.cv.yview_scroll(d * 2, "units"))
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    def _keys(self):
        b = self.bind
        b("<Escape>", lambda e: self.destroy()); b("<Alt-Left>", lambda e: self.back()); b("<Alt-Right>", lambda e: self.forward()); b("<Alt-Up>", lambda e: self.up())
        b("<Alt-Home>", lambda e: self.goto(("dir", Path.home())))
        b("<Control-l>", lambda e: self.edit_path()); b("<Control-L>", lambda e: self.edit_path()); b("<Control-f>", lambda e: self.toggle_search()); b("<Control-F>", lambda e: self.toggle_search())
        b("<Control-h>", lambda e: self.toggle_hidden()); b("<Control-H>", lambda e: self.toggle_hidden()); b("<Control-Shift-N>", lambda e: self.new_folder()); b("<Control-Shift-n>", lambda e: self.new_folder())
        for w in (self.tree, self.cv):
            w.bind("<Return>", lambda e: self.activate()); w.bind("<BackSpace>", lambda e: self.up()); w.bind("<F2>", lambda e: self.rename()); w.bind("<Delete>", lambda e: self.trash())
            w.bind("<Key>", self.type_ahead, add="+")

    # ------------------------------------------------------------------ navigation
    def goto(self, loc, push=True):
        if loc[0] == "dir":
            p = Path(loc[1])
            if not p.is_dir(): self.ctx.say("Files", f"“{p}” is not a folder or cannot be opened.", self); return
            try: os.listdir(p)
            except OSError as e: self.ctx.say("Files", f"Cannot open this folder:\n{e}", self); return
            loc = ("dir", p)
        if push:
            del self.hist[self.hi + 1:]
            if not self.hist or self.hist[-1] != loc: self.hist.append(loc)
            self.hi = len(self.hist) - 1
        self.loc = loc; self.sel = None
        if loc[0] in ("recent", "trash"): self.sort_key, self.sort_asc = "mod", False
        elif self.sort_key == "where" and loc[0] == "dir": self.sort_key, self.sort_asc = "name", True
        elif loc[0] == "dir" and self.sort_key == "mod" and self.sort_asc is False and push: self.sort_key, self.sort_asc = "name", True
        if self.search_row.winfo_ismapped() and loc[0] != "search": self.search.set("")
        self.fill(); self._pathbar(); self._side_mark(); self.b_back.set_enabled(self.hi > 0); self.b_fwd.set_enabled(self.hi < len(self.hist) - 1)

    def back(self):
        if self.hi > 0: self.hi -= 1; self.goto(self.hist[self.hi], push=False)

    def forward(self):
        if self.hi < len(self.hist) - 1: self.hi += 1; self.goto(self.hist[self.hi], push=False)

    def up(self):
        if self.loc[0] == "dir" and self.loc[1].parent != self.loc[1]: self.goto(("dir", self.loc[1].parent))
        elif self.loc[0] == "search": self.goto(("dir", self.loc[1]))

    def cwd(self):
        if self.loc[0] == "dir": return self.loc[1]
        if self.loc[0] == "search": return self.loc[1]
        return Path.home()

    # ------------------------------------------------------------------ path bar
    def _pathbar(self):
        P, ctx = self.P, self.ctx
        for w in self.bar.winfo_children(): w.destroy()
        def seg(text, loc, bold=False):
            l = tk.Label(self.bar, text=text, bg=P["card"], fg=P["text"], font=ctx.f_bold if bold else ctx.f_body, cursor="hand2", padx=5)
            l.pack(side="left"); l.bind("<Button-1>", lambda e: self.goto(loc))
            l.bind("<Enter>", lambda e: l.configure(bg=P["soft"])); l.bind("<Leave>", lambda e: l.configure(bg=P["card"]))
        def sep(): tk.Label(self.bar, text="/", bg=P["card"], fg=P["muted"], font=ctx.f_body).pack(side="left")
        kind = self.loc[0]
        if kind == "dir":
            p, home = self.loc[1], Path.home(); parts = []
            try: rel = p.relative_to(home); parts = [("Home", home)] + [(n, home.joinpath(*rel.parts[:i + 1])) for i, n in enumerate(rel.parts)]
            except ValueError:
                parts = [(p.anchor or "/", Path(p.anchor or "/"))] + [(n, Path(p.anchor or "/").joinpath(*p.parts[1:i + 2])) for i, n in enumerate(p.parts[1:])]
            if len(parts) > 4: parts = [("…", parts[-5][1])] + parts[-4:]
            for i, (n, pp) in enumerate(parts):
                if i: sep()
                seg(n, ("dir", pp), i == len(parts) - 1)
        else:
            seg({"recent": "Recent", "starred": "Starred", "network": "Network", "trash": "Trash", "search": "Search results"}[kind], self.loc, True)
        sp = tk.Label(self.bar, text="", bg=P["card"]); sp.pack(side="left", fill="x", expand=True); sp.bind("<Button-1>", lambda e: self.edit_path())

    def edit_path(self):
        if self.loc[0] != "dir": return
        for w in self.bar.winfo_children(): w.destroy()
        v = tk.StringVar(value=str(self.loc[1])); e = ttk.Entry(self.bar, textvariable=v, style="Modern.TEntry"); e.pack(fill="x", padx=4, ipady=1)
        e.focus_set(); e.select_range(0, "end")
        def go(_e=None):
            p = Path(os.path.expanduser(v.get().strip()))
            if p.is_dir(): self.goto(("dir", p))
            elif p.exists(): self.goto(("dir", p.parent)); self.name.set(p.name)
            else: self.ctx.say("Files", f"“{p}” does not exist.", self); self._pathbar()
        e.bind("<Return>", go); e.bind("<Escape>", lambda ev: (self._pathbar(), "break")[1]); e.bind("<FocusOut>", lambda ev: self.after(100, self._pathbar) if self.bar.winfo_exists() else None)

    # ------------------------------------------------------------------ listing
    def want(self, p, is_dir):
        if is_dir: return True
        if self.filter.get().startswith("Supported") and self.exts: return p.suffix.lower() in self.exts or p.name.lower().endswith(tuple(self.exts))
        return True

    def hidden_ok(self, name): return self.show_hidden.get() or not name.startswith(".")

    def fill(self):
        kind = self.loc[0]; ents = []
        if kind == "dir":
            try: names = os.listdir(self.loc[1])
            except OSError: names = []
            for n in names:
                if not self.hidden_ok(n): continue
                e = entry_of(self.loc[1] / n)
                if e and self.want(e.path, e.is_dir): ents.append(e)
        elif kind == "recent": ents = self._recent()
        elif kind == "starred":
            for s in self.cfg.get("starred", []):
                e = entry_of(Path(s), str(Path(s).parent))
                if e: ents.append(e)
        elif kind == "network": ents = [e for e in (entry_of(p, "") for _, p in network_places()) if e]
        elif kind == "trash": ents = self._trash()
        elif kind == "search": ents = list(self.entries) if hasattr(self, "_keep_search") else []
        self.entries = ents; self.sel = None
        self._sort(); self.render()

    def _recent(self):
        seen, out = {}, []
        for p, ts in self.cfg.get("recent", []): seen[p] = max(seen.get(p, 0), ts)
        if LINUX:
            try:
                import xml.etree.ElementTree as ET
                for b in ET.parse(Path.home() / ".local/share/recently-used.xbel").getroot().iter("bookmark"):
                    u = urlparse(b.get("href", ""))
                    if u.scheme == "file":
                        ts = datetime.datetime.fromisoformat((b.get("modified") or b.get("visited") or "1970-01-01T00:00:00Z").replace("Z", "+00:00")).timestamp()
                        seen[unquote(u.path)] = max(seen.get(unquote(u.path), 0), ts)
            except Exception: pass
        for p, ts in sorted(seen.items(), key=lambda kv: -kv[1])[:150]:
            path = Path(p)
            if path.is_file() and self.hidden_ok(path.name) and self.want(path, False):
                e = entry_of(path, str(path.parent))
                if e: e.mtime = ts or e.mtime; out.append(e)
        return out

    def _trash(self):
        base = trash_dir(); out = []
        if base is None:
            self.status.config(text="The Recycle Bin is managed by Windows: open it from the desktop."); return out
        files = base / "files" if LINUX else base
        try: names = os.listdir(files)
        except OSError: return out
        for n in names:
            if n.startswith(".") and not LINUX: continue
            e = entry_of(files / n, "", False)
            if not e: continue
            if LINUX:
                inf = base / "info" / (n + ".trashinfo"); e.info = str(inf)
                try:
                    kv = dict(l.split("=", 1) for l in inf.read_text().splitlines() if "=" in l)
                    e.where = str(Path(unquote(kv.get("Path", ""))).parent)
                    e.mtime = datetime.datetime.fromisoformat(kv["DeletionDate"]).timestamp()
                except Exception: pass
            out.append(e)
        return out

    # ------------------------------------------------------------------ sorting
    def _sort(self):
        k, asc = self.sort_key, self.sort_asc
        key = {"name": lambda e: e.name.lower(), "size": lambda e: (e.size if not e.is_dir else -1, e.name.lower()), "mod": lambda e: e.mtime, "where": lambda e: (e.where.lower(), e.name.lower())}[k]
        self.entries.sort(key=key, reverse=not asc)
        if self.loc[0] in ("dir", "search", "trash", "starred"): self.entries.sort(key=lambda e: not e.is_dir)    # folders first (stable)

    def sort_by(self, key):
        if not key: return
        if key == self.sort_key: self.sort_asc = not self.sort_asc
        else: self.sort_key, self.sort_asc = key, key in ("name", "size", "where")
        self._sort(); self.render()

    # ------------------------------------------------------------------ drawing
    def render(self):
        virtual = self.loc[0] != "dir"
        mode = self.view.get()
        self.list_box.pack_forget(); self.grid_box.pack_forget()
        (self.grid_box if mode == "grid" else self.list_box).pack(fill="both", expand=True)
        self.b_view.configure(text="☰" if mode == "grid" else "▦")
        tr = self.tree; tr.delete(*tr.get_children())
        tr.column("where", width=220 if virtual else 0, stretch=False)
        arrow = " ▲" if self.sort_asc else " ▼"
        for c, k in (("size", "size"), ("mod", "mod"), ("where", "where")): tr.heading(c, text={"size": "Size", "mod": "Modified", "where": "Location" if self.loc[0] != "trash" else "Original location"}[k] + (arrow if self.sort_key == k else ""))
        tr.heading("#0", text="Name" + (arrow if self.sort_key == "name" else ""))
        starred = set(self.cfg.get("starred", []))
        for i, e in enumerate(self.entries):
            sz = (f"{e.size} item{'s' if e.size != 1 else ''}" if e.is_dir and self.loc[0] != "trash" else ("" if e.is_dir else fmt_size(e.size)))
            tr.insert("", "end", iid=str(i), text="  " + e.name, image=self._icon("dir" if e.is_dir else "file"), values=(sz, fmt_time(e.mtime), e.where, "★" if str(e.path) in starred else "☆"),
                      tags=() if (self.mode == "save" or e.is_dir or self.want(e.path, False)) else ("dim",))
        self.draw_grid()
        n = len(self.entries)
        if not (self.loc[0] == "trash" and trash_dir() is None):
            self.status.config(text=("" if n else {"recent": "No recent files yet.", "starred": "Nothing is starred. Click the ☆ next to a file to star it.", "trash": "Trash is empty.", "network": "No network locations found (mounted network shares appear here).",
                                                   "search": "No results.", "dir": "This folder is empty."}.get(self.loc[0], "")) + (f"{n} item{'s' if n != 1 else ''}" if n else ""))

    def draw_grid(self):
        cv = self.cv; cv.delete("all"); P = self.P
        if self.view.get() != "grid": return
        W = max(200, cv.winfo_width()); tw, th = 120, 112; cols = max(1, W // tw)
        for i, e in enumerate(self.entries):
            x, y = (i % cols) * tw, (i // cols) * th; t = f"t{i}"
            if i == self.sel: cv.create_rectangle(x + 4, y + 4, x + tw - 4, y + th - 4, fill=P["sel"], outline=P["accent"], tags=(t,))
            else: cv.create_rectangle(x + 4, y + 4, x + tw - 4, y + th - 4, fill=P["card"], outline=P["card"], tags=(t,))
            cx, cy = x + tw / 2, y + 40
            if e.is_dir:
                cv.create_polygon(cx - 28, cy - 18, cx - 8, cy - 18, cx - 2, cy - 11, cx + 28, cy - 11, cx + 28, cy + 22, cx - 28, cy + 22, fill="#62a0ea", outline="#3584e4", width=2, tags=(t,))
            else:
                cv.create_polygon(cx - 20, cy - 26, cx + 8, cy - 26, cx + 20, cy - 14, cx + 20, cy + 26, cx - 20, cy + 26, fill="#f6f5f4", outline="#9a9996", width=2, tags=(t,))
                ext = e.path.suffix[1:6].upper()
                if ext: cv.create_text(cx, cy + 8, text=ext, fill="#77767b", font=(self.ctx.sans, 8, "bold"), tags=(t,))
            name = e.name if len(e.name) <= 26 else e.name[:12] + "…" + e.name[-11:]
            cv.create_text(cx, y + 80, text=name, fill=P["text"], font=self.ctx.f_small, width=tw - 14, justify="center", anchor="n", tags=(t,))
        cv.configure(scrollregion=(0, 0, W, ((len(self.entries) + cols - 1) // cols) * th + 8))

    # ------------------------------------------------------------------ selection
    def select(self, i):
        self.sel = i
        e = self.entries[i] if i is not None and i < len(self.entries) else None
        if e:
            if not e.is_dir or self.mode == "save" and False: self.name.set(e.name)
            self.status.config(text=f"“{e.name}” selected" + (f"  ·  {fmt_size(e.size)}" if not e.is_dir else f"  ·  {e.size} items"))
        if self.view.get() == "grid": self.draw_grid()
        elif i is not None and self.tree.exists(str(i)) and self.tree.selection() != (str(i),): self.tree.selection_set(str(i)); self.tree.see(str(i))

    def on_tree_select(self, _e=None):
        s = self.tree.selection()
        if s: self.select(int(s[0]))

    def on_tree_click(self, e):
        if self.tree.identify_region(e.x, e.y) == "cell" and self.tree.identify_column(e.x) == "#4":
            r = self.tree.identify_row(e.y)
            if r: self.toggle_star(self.entries[int(r)]); return "break"

    def on_double(self, e):
        if self.tree.identify_region(e.x, e.y) in ("tree", "cell") and self.tree.identify_row(e.y): self.activate()

    def cv_index(self, e):
        x, y = self.cv.canvasx(e.x), self.cv.canvasy(e.y); W = max(200, self.cv.winfo_width()); cols = max(1, W // 120)
        i = int(y // 112) * cols + int(x // 120)
        return i if 0 <= i < len(self.entries) and int(x // 120) < cols else None

    def on_cv_click(self, e):
        self.cv.focus_set(); i = self.cv_index(e); self.select(i) if i is not None else self.select(None)

    def on_cv_double(self, e):
        if self.cv_index(e) is not None: self.activate()

    def on_cv_right(self, e):
        i = self.cv_index(e); self.select(i) if i is not None else None; self.context(e, i)

    def on_right(self, e):
        r = self.tree.identify_row(e.y); i = int(r) if r else None
        if i is not None: self.select(i)
        self.context(e, i)

    def current(self): return self.entries[self.sel] if self.sel is not None and self.sel < len(self.entries) else None

    def type_ahead(self, e):
        if not e.char or not e.char.isprintable() or e.state & 0x4 or e.char in " \r": return
        now = time.time(); self.typed = (self.typed if now - self.typed_t < 1.0 else "") + e.char.lower(); self.typed_t = now
        for i, en in enumerate(self.entries):
            if en.name.lower().startswith(self.typed): self.select(i); break

    # ------------------------------------------------------------------ actions
    def activate(self):
        e = self.current()
        if e is None: return self.accept()
        if e.is_dir and self.loc[0] != "trash": self.goto(("dir", e.path))
        elif not e.is_dir and self.loc[0] != "trash": self.name.set(e.name); self._pick(e.path)

    def accept(self):
        text = self.name.get().strip(); e = self.current()
        if self.mode == "open":
            if e is not None and not e.is_dir and (not text or text == e.name): return self._pick(e.path)
            if not text: self.ctx.say("Open", "Choose a file first.", self); return
            p = Path(os.path.expanduser(text)); p = p if p.is_absolute() else self.cwd() / p
            if p.is_dir(): return self.goto(("dir", p))
            if p.is_file(): return self._pick(p)
            self.ctx.say("Open", f"“{p.name}” does not exist.", self); return
        if not text: self.ctx.say("Save", "Type a file name.", self); return
        p = Path(os.path.expanduser(text)); p = p if p.is_absolute() else self.cwd() / p
        if self.exts and not p.name.lower().endswith(tuple(self.exts)): p = p.with_name(p.name + self.exts[0])
        self._pick(p)

    def _pick(self, p):
        p = Path(p)
        if self.mode == "save":
            if p.is_dir(): return self.goto(("dir", p))
            if p.exists() and not self.ctx.ask("Replace file?", f"“{p.name}” already exists in this folder. Do you want to replace it?", self): return
            if not p.parent.is_dir(): self.ctx.say("Save", f"The folder “{p.parent}” does not exist.", self); return
        self.result = str(p); self.destroy()

    def toggle_star(self, e):
        s = list(self.cfg.get("starred", [])); k = str(e.path)
        if k in s: s.remove(k)
        else: s.append(k)
        self.cfg["starred"] = s; self.ctx.save_cfg()
        if self.loc[0] == "starred": self.fill()
        else: self.render(); (self.select(self.entries.index(e)) if e in self.entries else None)

    def new_folder(self):
        if self.loc[0] != "dir": return
        n = self.ctx.ask_string("New Folder", "Folder name:", "Untitled Folder")
        if n and n.strip():
            try: (self.loc[1] / n.strip()).mkdir()
            except OSError as ex: self.ctx.say("New Folder", str(ex), self); return
            self.fill(); [self.select(i) for i, e in enumerate(self.entries) if e.name == n.strip()]

    def rename(self):
        e = self.current()
        if e is None or self.loc[0] == "trash": return
        n = self.ctx.ask_string("Rename", f"New name for “{e.name}”:", e.name)
        if n and n.strip() and n.strip() != e.name:
            dest = e.path.with_name(n.strip())
            if dest.exists(): self.ctx.say("Rename", f"“{dest.name}” already exists.", self); return
            try: e.path.rename(dest)
            except OSError as ex: self.ctx.say("Rename", str(ex), self); return
            for key in ("starred",):
                s = [str(dest) if x == str(e.path) else x for x in self.cfg.get(key, [])]; self.cfg[key] = s
            self.fill(); [self.select(i) for i, x in enumerate(self.entries) if x.name == dest.name]

    def trash(self):
        e = self.current()
        if e is None: return
        if self.loc[0] == "trash": return self.delete_forever()
        try: trash_move(e.path)
        except OSError as ex:
            if self.ctx.ask("Move to Trash", f"Could not move “{e.name}” to the Trash ({ex}).\nDelete it permanently instead?", self): self._rm(e.path)
            else: return
        self.cfg["starred"] = [x for x in self.cfg.get("starred", []) if x != str(e.path)]; self.fill()

    @staticmethod
    def _rm(p):
        shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()

    def delete_forever(self):
        e = self.current()
        if e is None or self.loc[0] != "trash": return
        if self.ctx.ask("Delete permanently?", f"“{e.name}” will be deleted forever. This cannot be undone.", self):
            try: self._rm(e.path); Path(e.info).unlink(missing_ok=True) if e.info else None
            except OSError as ex: self.ctx.say("Delete", str(ex), self)
            self.fill()

    def restore(self):
        e = self.current()
        if e is None or not e.info: return
        try:
            kv = dict(l.split("=", 1) for l in Path(e.info).read_text().splitlines() if "=" in l); dest = Path(unquote(kv["Path"]))
            if dest.exists(): self.ctx.say("Restore", f"“{dest}” already exists.", self); return
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(e.path), str(dest)); Path(e.info).unlink(missing_ok=True)
        except Exception as ex: self.ctx.say("Restore", str(ex), self); return
        self.fill()

    def empty_trash(self):
        if not self.entries or not self.ctx.ask("Empty Trash?", "All items in the Trash will be deleted forever.", self): return
        for e in list(self.entries):
            try: self._rm(e.path); Path(e.info).unlink(missing_ok=True) if e.info else None
            except OSError: pass
        self.fill()

    def properties(self, e=None):
        e = e or self.current()
        if e is None: return
        kind = "Folder" if e.is_dir else (e.path.suffix[1:].upper() + " file" if e.path.suffix else "File")
        size = f"{e.size} items" if e.is_dir else f"{fmt_size(e.size)} ({e.size:,} bytes)"
        self.ctx.say("Properties", f"Name:  {e.name}\nType:  {kind}\nSize:  {size}\nLocation:  {e.path.parent}\nModified:  {fmt_time(e.mtime)}", self)

    def copy_path(self, e):
        self.clipboard_clear(); self.clipboard_append(str(e.path)); self.status.config(text="Path copied to the clipboard.")

    # ------------------------------------------------------------------ menus
    def toggle_hidden(self):
        self.show_hidden.set(not self.show_hidden.get()); self.cfg["fd_hidden"] = self.show_hidden.get(); self.fill()

    def toggle_view(self):
        self.view.set("grid" if self.view.get() == "list" else "list"); self.cfg["fd_view"] = self.view.get(); self.render()

    def sort_menu(self, parent):
        m = self.ctx.menu()
        for label, k in (("Name", "name"), ("Size", "size"), ("Modified", "mod")): m.add_command(label=("✔  " if self.sort_key == k else "    ") + label, command=lambda k=k: (setattr(self, "sort_key", k), self._sort(), self.render()))
        m.add_separator(); m.add_command(label=("✔  " if self.sort_asc else "    ") + "Ascending", command=lambda: (setattr(self, "sort_asc", True), self._sort(), self.render()))
        m.add_command(label=("✔  " if not self.sort_asc else "    ") + "Descending", command=lambda: (setattr(self, "sort_asc", False), self._sort(), self.render()))
        return m

    def main_menu(self):
        m = self.ctx.menu()
        m.add_command(label="New Folder…", command=self.new_folder, state="normal" if self.loc[0] == "dir" else "disabled", accelerator="Ctrl+Shift+N")
        m.add_checkbutton(label="Show Hidden Files", variable=self.show_hidden, command=self.toggle_hidden, accelerator="Ctrl+H")
        m.add_cascade(label="Sort by", menu=self.sort_menu(m))
        m.add_command(label="Icon view" if self.view.get() == "list" else "List view", command=self.toggle_view)
        if self.loc[0] == "trash": m.add_separator(); m.add_command(label="Empty Trash…", command=self.empty_trash)
        m.add_separator(); m.add_command(label="Go to Home", command=lambda: self.goto(("dir", Path.home())))
        b = self.winfo_pointerxy(); m.tk_popup(*b)

    def side_menu(self, e, loc):
        m = self.ctx.menu()
        if loc[0] == "trash": m.add_command(label="Empty Trash…", command=lambda: (self.goto(loc), self.empty_trash()))
        else: m.add_command(label="Open", command=lambda: self.goto(loc))
        m.tk_popup(e.x_root, e.y_root)

    def context(self, e, i):
        m = self.ctx.menu(); en = self.entries[i] if i is not None and i < len(self.entries) else None; kind = self.loc[0]
        if en:
            if kind == "trash":
                m.add_command(label="Restore", command=self.restore, state="normal" if en.info else "disabled"); m.add_command(label="Delete Permanently…", command=self.delete_forever)
            else:
                m.add_command(label="Open" if en.is_dir else ("Select" if self.mode == "open" else "Use this name"), command=self.activate)
                if kind != "dir": m.add_command(label="Open Containing Folder", command=lambda: self.goto(("dir", en.path.parent if not en.is_dir else en.path.parent)))
                m.add_separator()
                m.add_command(label="Rename…", command=self.rename, accelerator="F2"); m.add_command(label="Move to Trash", command=self.trash, accelerator="Delete")
                m.add_command(label=("Unstar" if str(en.path) in self.cfg.get("starred", []) else "Star"), command=lambda: self.toggle_star(en))
                m.add_command(label="Copy Path", command=lambda: self.copy_path(en))
            m.add_separator(); m.add_command(label="Properties", command=lambda: self.properties(en))
        else:
            m.add_command(label="New Folder…", command=self.new_folder, state="normal" if kind == "dir" else "disabled")
            m.add_checkbutton(label="Show Hidden Files", variable=self.show_hidden, command=self.toggle_hidden)
            m.add_cascade(label="Sort by", menu=self.sort_menu(m))
            if kind == "trash": m.add_command(label="Empty Trash…", command=self.empty_trash)
        m.tk_popup(e.x_root, e.y_root)

    # ------------------------------------------------------------------ search
    def toggle_search(self):
        if self.search_row.winfo_ismapped():
            self.search_row.pack_forget(); self.search.set("")
            if self.loc[0] == "search": self.goto(("dir", self.loc[1]))
            self.tree.focus_set()
        else:
            self.search_row.pack(fill="x", after=self.bar.master, pady=(0, 6)); self.search_ent.focus_set()

    def _search_later(self):
        if hasattr(self, "_st"): self.after_cancel(self._st)
        self._st = self.after(300, self.run_search)

    def run_search(self):
        q = self.search.get().strip().lower()
        root = self.loc[1] if self.loc[0] in ("dir", "search") else Path.home()
        self.search_gen += 1; gen = self.search_gen
        hid = self.show_hidden.get(); filt = self.filter.get().startswith("Supported") and bool(self.exts); exts = tuple(self.exts)
        if not q:
            if self.loc[0] == "search": self.goto(("dir", root))
            return
        self.loc = ("search", root); self.entries = []; self._keep_search = True; self.sel = None; self._pathbar(); self._side_mark(); self.render()
        self.status.config(text="Searching…")
        def work():
            scanned, found = 0, 0
            for dp, dns, fns in os.walk(root):
                if gen != self.search_gen: return
                dns[:] = [d for d in dns if hid or not d.startswith(".")]
                for n in dns + fns:
                    scanned += 1
                    if q in n.lower() and (hid or not n.startswith(".")):
                        e = entry_of(Path(dp) / n, str(Path(dp)), False)
                        if e and (e.is_dir or not filt or e.path.name.lower().endswith(exts)): self.q.put((gen, e)); found += 1
                if scanned > 40000 or found >= 400: break
            self.q.put((gen, None))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        if not self.winfo_exists(): return
        try:
            got = False; done = False
            while True:
                gen, e = self.q.get_nowait()
                if gen != self.search_gen: continue
                if e is None: done = True
                else: self.entries.append(e); got = True
        except queue.Empty: pass
        if got or done:
            self._sort(); self.render()
            if done: self.status.config(text=(f"{len(self.entries)} result{'s' if len(self.entries) != 1 else ''}" if self.entries else "No results."))
        self.after(150, self._poll)
