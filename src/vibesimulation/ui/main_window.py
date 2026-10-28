"""The application shell: top menu bar + one page at a time (Home, Logisim, Import & AI, Multisim, VLSI, Settings)."""
import time
import tkinter as tk

from ..core.document import Document
from ..analog.document import AnalogDocument
from ..systemverilog.document import SvDocument
from ..vlsi.document import VlsiDocument
from .actions import AnalogActions, FileActions
from .commands import Palette, build_commands, shortcuts_sheet
from .context import UiContext
from .menubar import MenuBar
from .rail import Rail
from .sidebar import SideBar
from .pages.home_page import HomePage
from .ai_import.import_page import ImportPage
from .multisim.workspace import MultisimPage
from .settings.page import SettingsPage
from .logisim.workspace import WorkspacePage
from .systemverilog.actions import SystemVerilogActions
from .systemverilog.workspace import SystemVerilogPage
from .vlsi.actions import VlsiActions
from .vlsi.workspace import VlsiPage
from .theme import SCALES, system_dark

WORKSPACES = ("logisim", "multisim", "vlsi", "systemverilog")        # the pages the menus and shortcuts act on
TITLES = {"home": "Home", "logisim": "Logisim", "import": "Import & AI", "multisim": "Multisim", "vlsi": "VLSI", "systemverilog": "SystemVerilog", "settings": "Settings"}


class MainWindow:
    def __init__(self, root):
        self.root = root; root.title("VibeSimulation"); root.minsize(900, 600)
        self.ctx = ctx = UiContext(root); ctx.apply(); self.palette = None; self._sys_check = 0
        g = ctx.cfg.get("geometry") if ctx.cfg.get("remember_window", True) else None
        root.geometry(g if isinstance(g, str) and g.count("x") == 1 and "+" in g else "1360x860")
        self.doc = Document(); self.adoc = AnalogDocument(); self.vdoc = VlsiDocument(); self.sdoc = SvDocument()      # one document per section: they never share circuits
        self.top = tk.Frame(root, bd=0); self.top.pack(side="top", fill="x")                 # menu bar row, full width like VS Code
        self.bottom = tk.Frame(root, bd=0); self.bottom.pack(side="bottom", fill="x")        # status bar row
        self.mid = tk.Frame(root, bd=0); self.mid.pack(side="top", fill="both", expand=True)
        self.rail = Rail(ctx, self.mid, self)
        self.side = SideBar(ctx, self.mid, self)
        self.col = tk.Frame(self.mid, bd=0); self.col.pack(side="left", fill="both", expand=True)
        self.handle = tk.Label(self.mid, text="‹", cursor="hand2", bd=0, font=ctx.f_icon); self.handle.bind("<Button-1>", lambda e: self.toggle_side())
        self.rail.bind("<Configure>", lambda e: self.place_handle(), add="+"); ctx.themed.append(self.paint_handle)
        self.place_rail()
        self.stage = tk.Frame(self.col, bd=0)
        self.pages, self.current = {}, None
        # pages are built before the menu bar because the View menu reads the workspace
        self.pages["logisim"] = WorkspacePage(ctx, self.stage, self)
        self.actions = FileActions(ctx, self.doc, self.pages["logisim"].views["table"])
        for v in self.pages["logisim"].views.values():
            if hasattr(v, "main"): v.main = self
        self.pages["home"] = HomePage(ctx, self.stage, self)
        self.pages["import"] = ImportPage(ctx, self.stage, self)
        self.pages["multisim"] = MultisimPage(ctx, self.stage, self)
        self.aactions = AnalogActions(ctx, self.adoc, self.pages["multisim"].views["results"])
        for v in self.pages["multisim"].views.values():
            if hasattr(v, "main"): v.main = self
        self.pages["vlsi"] = VlsiPage(ctx, self.stage, self)
        self.vactions = VlsiActions(ctx, self.vdoc, self.pages["vlsi"].views["table"])
        for v in self.pages["vlsi"].views.values():
            if hasattr(v, "main"): v.main = self
        self.pages["systemverilog"] = SystemVerilogPage(ctx, self.stage, self)
        self.sactions = SystemVerilogActions(ctx, self.sdoc, self.pages["systemverilog"].views["table"])
        for v in self.pages["systemverilog"].views.values():
            if hasattr(v, "main"): v.main = self
        self.pages["settings"] = SettingsPage(ctx, self.stage, self)
        self.commands = build_commands(self)
        self.menubar = MenuBar(ctx, self.top, self); self.menubar.pack(fill="x"); self.menubar.line.pack(in_=self.top, fill="x")
        self.status = StatusBar(ctx, self.bottom, self); self.status.place_bar()
        self.stage.pack(fill="both", expand=True)
        self._bind_keys()
        ctx.themed.append(lambda: [w.configure(bg=ctx.P["bg"]) for w in (root, self.stage, self.col, self.mid, self.top, self.bottom)])
        ctx.apply(); self.adoc.load_sample(); self.vdoc.load_sample(); self.sdoc.load_sample(); self.doc.load_sample()
        self.show("home")
        from .product.hooks import ProductHooks
        self.hooks = ProductHooks(self); self.hooks.start()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<FocusIn>", self._focus_in, add="+"); root.after(6000, self._watch_system)

    # ---- keyboard
    def _bind_keys(self):
        root = self.root
        def kbd(v):
            def f(e):
                if self.ctx.kbd != v:
                    self.ctx.kbd = v
                    w = root.focus_get()
                    if w is not None and hasattr(w, "draw"):
                        try: w.draw()
                        except Exception: pass
            return f
        root.bind_all("<KeyPress-Tab>", kbd(True), add="+"); root.bind_all("<ISO_Left_Tab>", kbd(True), add="+"); root.bind_all("<ButtonPress>", kbd(False), add="+")
        def fire(c, e=None):
            if e is not None and e.widget.winfo_toplevel() is not root: return "break"
            root.after(1, c.fn); return "break"
        for c in self.commands:
            for seq in c.seqs:
                root.bind(seq, lambda e, c=c: fire(c, e))
                for cls in ("Text", "Entry", "TEntry", "TCombobox", "Listbox"):      # beat Tk's emacs-style keys (Ctrl+K, Ctrl+O, Ctrl+N ...)
                    try: root.bind_class(cls, seq, lambda e, c=c: fire(c, e))
                    except tk.TclError: pass
        for mod in ("Control", "Command"):
            for key, fn in (("z", self.undo), ("y", self.redo), ("Z", self.redo)):
                try: root.bind(f"<{mod}-Key-{key}>", lambda e, fn=fn: fn())
                except tk.TclError: pass
        root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False) if root.attributes("-fullscreen") and e.widget.winfo_toplevel() is root else None, add="+")
        root.bind("<Control-Key-f>", lambda e: self.pages["settings"].focus_search() if self.current == "settings" else None)
        for k, name in (("f", "File"), ("e", "Edit"), ("v", "View"), ("p", "Project"), ("l", "Place"), ("s", "Simulate"), ("t", "Transfer"), ("o", "Tools"), ("h", "Help")):
            root.bind(f"<Alt-Key-{k}>", lambda e, n=name: self.menubar.open_label(n))
        for cls in ("Text", "Entry", "TEntry"): root.bind_class(cls, "<Button-3>", self._text_menu)

    def _text_menu(self, e):
        w = e.widget; w.focus_set(); m = self.ctx.menu(); ro = str(w.cget("state")) == "disabled" if "state" in w.keys() else False
        for lab, ev in (("Cut", "<<Cut>>"), ("Copy", "<<Copy>>"), ("Paste", "<<Paste>>")):
            m.add_command(label=lab, command=lambda ev=ev: w.event_generate(ev), state="disabled" if ro and lab != "Copy" else "normal")
        m.add_separator()
        m.add_command(label="Select all", command=lambda: (w.tag_add("sel", "1.0", "end-1c") if w.winfo_class() == "Text" else w.select_range(0, "end")))
        m.tk_popup(e.x_root, e.y_root); return "break"

    def toggle_fullscreen(self): self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))

    def open_palette(self):
        if self.palette is not None: self.palette.close(); return
        self.palette = Palette(self)

    def show_shortcuts(self): shortcuts_sheet(self)

    def show_about(self):
        from .product.about import AboutBox
        AboutBox(self.ctx, self)

    def show_gallery(self, section=None):
        from .product.gallery import GalleryBox
        GalleryBox(self.ctx, self, section)

    def restore_focus(self):
        try: self.root.focus_set()
        except tk.TclError: pass

    # ---- look
    def zoom(self, d):
        cur = int(self.ctx.cfg.get("text_scale", 100)); i = min(range(len(SCALES)), key=lambda k: abs(SCALES[k] - cur))
        new = 100 if d == 0 else SCALES[max(0, min(len(SCALES) - 1, i + d))]
        self.set_pref("text_scale", new); self.ctx.toast(f"Text size {new}%")

    def set_pref(self, key, value):
        self.ctx.cfg[key] = value; self.ctx.save_cfg(); self.ctx.refresh(); self.after_look()

    def place_rail(self):
        right = self.ctx.cfg.get("rail_side", "Left") == "Right"
        self.rail.pack_forget(); self.rail.pack(side="right" if right else "left", fill="y", before=self.col)
        self.col.pack_configure(padx=(0, 0) if right else (0, 0))
        self.place_side()

    # ---- the side bar (Explorer area): Logisim's explorer, Multisim's component database
    def side_open(self): return bool(self.ctx.cfg.get("side_open", True)) and self.side.kind_for(self.current or "home") is not None

    def place_side(self):
        right = self.ctx.cfg.get("rail_side", "Left") == "Right"
        self.side.pack_forget(); self.side.sash.pack_forget()
        cur = getattr(self, "current", None)
        if cur and self.side.kind_for(cur) and self.ctx.cfg.get("side_open", True):
            self.side.show_for(cur)
            if right: self.side.pack(side="right", fill="y", before=self.col); self.side.sash.pack(side="right", fill="y", before=self.side)
            else: self.side.pack(side="left", fill="y", before=self.col); self.side.sash.pack(side="left", fill="y", before=self.col)
        self.place_handle()

    def place_handle(self):
        """The small accent tab on the edge of the side panel: click it to hide or show the panel (works on every page that has one)."""
        cur = getattr(self, "current", None)
        if not (cur and self.side.kind_for(cur)): self.handle.place_forget(); return
        right = self.ctx.cfg.get("rail_side", "Left") == "Right"; rw = max(1, int(self.rail["width"])); opened = bool(self.ctx.cfg.get("side_open", True))
        self.handle.configure(text=("›" if right else "‹") if opened else ("‹" if right else "›"))
        h = self.ctx.dp(52)
        if right: self.handle.place(in_=self.mid, relx=1.0, x=-rw, rely=0.5, anchor="e", width=self.ctx.dp(15), height=h)
        else: self.handle.place(in_=self.mid, x=rw, rely=0.5, anchor="w", width=self.ctx.dp(15), height=h)
        self.handle.lift()

    def paint_handle(self):
        P = self.ctx.P; self.handle.configure(bg=P["accent"], fg=P["accent_fg"])

    def toggle_side(self):
        self.ctx.cfg["side_open"] = not self.ctx.cfg.get("side_open", True); self.ctx.save_cfg(); self.place_side()

    def show_side(self, on=True):
        self.ctx.cfg["side_open"] = on; self.ctx.save_cfg(); self.place_side()

    def activity(self, key):
        """A click on an activity-bar icon: go there; clicking the icon of the page you are on shows / hides its side bar (like VS Code)."""
        if key == self.current and self.side.kind_for(key): self.toggle_side()
        else: self.show(key)

    def manage_menu(self, x, y):
        m = self.ctx.menu()
        m.add_command(label="Command palette…", accelerator="Ctrl+K", command=self.open_palette)
        m.add_separator()
        m.add_command(label="Settings", accelerator="Ctrl+,", command=lambda: self.show("settings"))
        m.add_command(label="Keyboard shortcuts", accelerator="F1", command=self.show_shortcuts)
        th = self.ctx.menu()
        for mode, name in (("light", "Light"), ("dark", "Dark"), ("system", "Match system")): th.add_command(label=name + ("   ✓" if self.ctx.mode == mode else ""), command=lambda mode=mode: self.set_pref("mode", mode))
        m.add_cascade(label="Theme", menu=th)
        m.add_separator()
        m.add_command(label="Make text larger", accelerator="Ctrl+=", command=lambda: self.zoom(1)); m.add_command(label="Make text smaller", accelerator="Ctrl+-", command=lambda: self.zoom(-1))
        m.tk_popup(x, y)

    def after_look(self):
        self.place_rail(); self.root.update_idletasks(); self.status.refresh()
        if self.current == "settings": self.pages["settings"].refresh()

    def reset_look(self):
        for k in ("mode", "accent", "corners", "density", "text_scale", "font", "reduce_motion", "high_contrast", "theme", "rail_size", "rail_side"): self.ctx.cfg.pop(k, None)
        self.ctx.save_cfg(); self.ctx.refresh(); self.after_look(); self.ctx.toast("Appearance reset")

    def _focus_in(self, e):
        if e.widget is self.root and time.time() - self._sys_check > 2: self._check_system()

    def _check_system(self):
        self._sys_check = time.time()
        if self.ctx.mode == "system" and system_dark() != self.ctx.dark: self.ctx.refresh(); self.after_look()

    def _watch_system(self):
        try:
            if self.ctx.mode == "system": self._check_system()
            self.root.after(6000, self._watch_system)
        except tk.TclError: pass

    # ---- navigation
    def show(self, name):
        if self.current: self.pages[self.current].pack_forget()
        self.current = name; self.pages[name].pack(fill="both", expand=True)
        self.publish_project()
        self.menubar.set_page(name, TITLES[name]); self.rail.set(name); self.place_side()
        if name == "settings": self.pages[name].refresh()
        self.status.refresh()
        try: self.pages[name].focus_first()
        except AttributeError: pass

    def open_image(self):
        self.show("import"); self.pages["import"].view.pick_image()

    # ---- the workspace being used decides which document / actions the menus act on
    def cur_actions_for_logisim(self): return self.actions

    def analog(self): return self.current == "multisim"

    def vlsi(self): return self.current in ("vlsi", "systemverilog")

    def workspace_key(self):
        """The workspace the menus act on: the page being shown if it is one, else Logisim."""
        return self.current if self.current in WORKSPACES else "logisim"

    def active(self): return self.pages[self.workspace_key()]

    def cur_doc(self): return {"multisim": self.adoc, "vlsi": self.vdoc, "systemverilog": self.sdoc}.get(self.workspace_key(), self.doc)

    def publish_project(self):
        """Subcircuit lookups are global: point them at the circuits of the section being shown."""
        d = self.cur_doc()
        if hasattr(d, "_publish") and self.workspace_key() != "multisim": d._publish()

    def actions_for(self, which): return {"multisim": self.aactions, "vlsi": self.vactions, "systemverilog": self.sactions}.get(which, self.actions)

    @property
    def cur_actions(self): return self.actions_for(self.workspace_key())

    # ---- editing
    def undo(self):
        self.active().editor().flush(); self.cur_doc().undo()

    def redo(self):
        self.active().editor().flush(); self.cur_doc().redo()

    # ---- settings / theme
    def toggle_dark(self):
        self.ctx.toggle(); self.ctx.save_cfg(); self.after_look()

    def apply_settings(self):
        w = self.pages["logisim"]
        for page in (w, self.pages["vlsi"], self.pages["systemverilog"]):
            t = page.views["table"]; t.show_mid.set(self.ctx.cfg.get("show_mid", True)); t.rebuild(); page.views["circuit"].draw()
        self.adoc.notify("changed")

    def close(self):
        self.hooks.finish()
        self.pages["import"].view.settings()
        try:
            if not self.root.attributes("-fullscreen"): self.ctx.cfg["geometry"] = self.root.winfo_geometry()
        except tk.TclError: pass
        self.ctx.save_cfg(); self.root.destroy()


class StatusBar(tk.Frame):
    """Slim bar at the bottom: where you are, and clickable hints for the command palette, shortcuts and text size."""
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.sh = ctx, shell
        self.left = tk.Label(self, anchor="w", font=ctx.f_small); self.left.pack(side="left", padx=14, pady=3)
        self.items = []
        for text, fn in (("Ctrl+K  Commands", shell.open_palette), ("F1  Shortcuts", shell.show_shortcuts), ("", lambda: shell.zoom(0))):
            l = tk.Label(self, text=text, font=ctx.f_small, cursor="hand2", padx=8); l.pack(side="right", pady=3); l.bind("<Button-1>", lambda e, fn=fn: fn())
            l.bind("<Enter>", lambda e, l=l: l.configure(bg=self.ctx.P["accent_h"] if "accent_h" in self.ctx.P else self.ctx.P["accent"])); l.bind("<Leave>", lambda e, l=l: l.configure(bg=self.ctx.P["accent"])); self.items.append(l)
        ctx.themed.append(self.paint); self.paint()

    def place_bar(self):
        self.sync()

    def sync(self):
        show = self.ctx.cfg.get("show_status", True)
        if show and not self.winfo_ismapped(): self.pack(side="bottom", fill="x")
        elif not show and self.winfo_ismapped(): self.pack_forget()

    def refresh(self):
        c = self.ctx; self.sync()
        self.left.configure(text=f"{TITLES.get(self.sh.current, '')}    ·    {c.mode_label()} theme")
        self.items[2].configure(text=f"Text {c.cfg.get('text_scale', 100)}%")

    def paint(self):
        P = self.ctx.P; bg = P["accent"]; fg = P["accent_fg"]; self.configure(bg=bg); self.left.configure(bg=bg, fg=fg)
        for l in self.items: l.configure(bg=bg, fg=fg)


def main():
    root = tk.Tk(); MainWindow(root); root.mainloop()
