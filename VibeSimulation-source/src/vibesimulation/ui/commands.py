"""Every action of the app in one list: used for keyboard shortcuts, the Ctrl+K command palette, menus and the shortcut sheet."""
import tkinter as tk

from .shapes import rrect
from .theme import ACCENTS, DENSITY, RADII, SCALES
from .widgets import Btn


class Command:
    def __init__(self, group, title, fn, keys="", seqs=(), hint=""):
        self.group, self.title, self.fn, self.keys, self.seqs, self.hint = group, title, fn, keys, tuple(seqs), hint


def build_commands(sh):
    """The command list for MainWindow `sh` (functions look the current workspace up when they run)."""
    ctx = sh.ctx; C = Command; L = []
    def add(*a, **k): L.append(C(*a, **k))
    for key, name, k, seq in (("home", "Home", "Ctrl+1", "<Control-Key-1>"), ("logisim", "Logisim workspace", "Ctrl+2", "<Control-Key-2>"),
                              ("import", "Import & AI", "Ctrl+3", "<Control-Key-3>"), ("multisim", "Multisim workspace", "Ctrl+4", "<Control-Key-4>"), ("vlsi", "VLSI workspace", "Ctrl+5", "<Control-Key-5>"),
                              ("settings", "Settings", "Ctrl+,", "<Control-Key-comma>")):
        add("Go to", name, lambda key=key: sh.show(key), k, [seq], "navigate")
    pg = sh.workspace_key
    add("File", "New blank circuit", lambda: (sh.cur_actions.new(), sh.show(pg())), "Ctrl+N", ["<Control-Key-n>"])
    add("File", "Open circuit JSON…", lambda: sh.cur_actions.json_open() and sh.show(pg()), "Ctrl+O", ["<Control-Key-o>"])
    add("File", "Open image (AI import)…", sh.open_image, "Ctrl+I", ["<Control-Key-i>"], "picture photo screenshot")
    add("File", "Save circuit JSON…", lambda: sh.cur_actions.json_save(), "Ctrl+S", ["<Control-Key-s>"])
    add("Download", "Download circuit (.circ for Logisim / .cir for Multisim)", lambda: (sh.aactions.cir() if sh.analog() else sh.cur_actions.circ()), "Ctrl+E", ["<Control-Key-e>"], "export")
    add("VLSI", "Open Verilog file (.v)…", lambda: sh.vactions.verilog_open() and sh.show("vlsi"), "", [], "hdl module")
    add("VLSI", "Download Verilog (.v)", lambda: sh.vactions.verilog_save(), "", [], "hdl module export")
    add("Download", "Download PDF (circuit + truth table)", lambda: sh.cur_actions.pdf(), "Ctrl+P", ["<Control-Key-p>"], "print export")
    add("Download", "Download truth table / results (.csv)", lambda: sh.cur_actions.csv(), "", [], "excel")
    add("Help", "Examples gallery…", sh.show_gallery, "", [], "tutorial sample learn")
    add("Help", "About VibeSimulation (version, updates)…", sh.show_about, "", [], "version update")
    add("Edit", "Undo", sh.undo, "Ctrl+Z"); add("Edit", "Redo", sh.redo, "Ctrl+Y")
    add("View", "Toggle full screen", sh.toggle_fullscreen, "F11", ["<F11>"])
    add("View", "Make text larger", lambda: sh.zoom(1), "Ctrl+=", ["<Control-Key-equal>", "<Control-Key-plus>", "<Control-Key-KP_Add>"], "zoom bigger")
    add("View", "Make text smaller", lambda: sh.zoom(-1), "Ctrl+-", ["<Control-Key-minus>", "<Control-Key-KP_Subtract>"], "zoom smaller")
    add("View", "Reset text size", lambda: sh.zoom(0), "Ctrl+0", ["<Control-Key-0>"], "zoom")
    add("View", "Toggle dark / light mode", sh.toggle_dark, "Ctrl+Shift+D", ["<Control-Shift-Key-D>", "<Control-Shift-Key-d>"], "theme")
    for m, n in (("light", "Light"), ("dark", "Dark"), ("system", "Match system")): add("Appearance", f"Theme: {n}", lambda m=m: sh.set_pref("mode", m), hint="mode dark light system")
    for a in ACCENTS: add("Appearance", f"Accent colour: {a}", lambda a=a: sh.set_pref("accent", a), hint="color")
    for r in RADII: add("Appearance", f"Corners: {r}", lambda r=r: sh.set_pref("corners", r), hint="round")
    for d in DENSITY: add("Appearance", f"Density: {d}", lambda d=d: sh.set_pref("density", d), hint="spacing compact")
    add("View", "Reset pane layout", lambda: sh.active().reset())
    add("View", "Reset appearance to defaults", sh.reset_look)
    add("Help", "Keyboard shortcuts", sh.show_shortcuts, "F1", ["<F1>", "<Control-Key-slash>"])
    add("Help", "Command palette", sh.open_palette, "Ctrl+K", ["<Control-Key-k>", "<Control-Shift-Key-P>", "<Control-Shift-Key-p>"])
    add("File", "Exit", sh.close, "Ctrl+Q", ["<Control-Key-q>"])
    return L


class Palette(tk.Frame):
    """Ctrl+K overlay: type to filter every command, Up/Down to move, Enter to run, Esc to close."""
    def __init__(self, sh):
        ctx = sh.ctx; P = ctx.P; root = ctx.root
        super().__init__(root, bd=0, bg=P["border"]); self.sh, self.ctx = sh, ctx
        self.box = tk.Frame(self, bg=P["card"], bd=0); self.box.pack(padx=1, pady=1)
        top = tk.Frame(self.box, bg=P["card"]); top.pack(fill="x", padx=14, pady=(14, 6))
        tk.Label(top, text="⌕", bg=P["card"], fg=P["muted"], font=ctx.f_icon).pack(side="left", padx=(0, 8))
        self.q = tk.StringVar(); self.q.trace_add("write", lambda *a: self.filter())
        self.e = tk.Entry(top, textvariable=self.q, bd=0, highlightthickness=0, bg=P["card"], fg=P["text"], insertbackground=P["text"], font=ctx.f_title, width=44)
        self.e.pack(side="left", fill="x", expand=True, ipady=4)
        tk.Frame(self.box, bg=P["border"], height=1).pack(fill="x")
        self.lb = tk.Listbox(self.box, bd=0, highlightthickness=0, activestyle="none", height=11, font=ctx.f_body, bg=P["card"], fg=P["text"],
                             selectbackground=P["accent"], selectforeground=P["accent_fg"], exportselection=False, selectborderwidth=0)
        self.lb.pack(fill="both", padx=6, pady=6)
        self.foot = tk.Label(self.box, text="↑↓ choose    Enter run    Esc close", bg=P["card"], fg=P["muted"], font=ctx.f_small, anchor="w"); self.foot.pack(fill="x", padx=14, pady=(0, 10))
        for k, fn in (("<Escape>", lambda e: self.close()), ("<Down>", lambda e: self.move(1)), ("<Up>", lambda e: self.move(-1)),
                      ("<Return>", lambda e: self.run()), ("<KP_Enter>", lambda e: self.run()), ("<Next>", lambda e: self.move(8)), ("<Prior>", lambda e: self.move(-8))):
            self.e.bind(k, lambda ev, fn=fn: (fn(ev), "break")[1])
        self.lb.bind("<ButtonRelease-1>", lambda e: self.run(self.lb.nearest(e.y))); self.lb.bind("<Motion>", lambda e: self.hover(self.lb.nearest(e.y)))
        self.items = []; self.filter()
        self.place(relx=0.5, y=70, anchor="n"); self.lift(); self.e.focus_set()
        self._click = root.bind("<ButtonPress-1>", self._outside, add="+")

    def hover(self, i):
        if 0 <= i < len(self.items): self.lb.selection_clear(0, "end"); self.lb.selection_set(i)

    def _outside(self, e):
        w = e.widget
        while w is not None:
            if w is self: return
            w = getattr(w, "master", None)
        self.close()

    def filter(self):
        terms = self.q.get().lower().split(); cmds = self.sh.commands
        def hay(c): return f"{c.group} {c.title} {c.hint}".lower()
        self.items = [c for c in cmds if all(t in hay(c) for t in terms)]
        self.lb.delete(0, "end")
        for c in self.items:
            self.lb.insert("end", f"  {c.group}  ›  {c.title}" + (f"        {c.keys}" if c.keys else ""))
        if self.items: self.lb.selection_set(0)

    def move(self, d):
        if not self.items: return
        cur = self.lb.curselection(); i = max(0, min(len(self.items) - 1, (cur[0] if cur else 0) + d))
        self.lb.selection_clear(0, "end"); self.lb.selection_set(i); self.lb.see(i)

    def run(self, i=None):
        cur = self.lb.curselection(); i = i if i is not None else (cur[0] if cur else None)
        if i is None or not (0 <= i < len(self.items)): return
        c = self.items[i]; self.close(); self.ctx.root.after(30, c.fn)

    def close(self):
        try: self.ctx.root.unbind("<ButtonPress-1>", self._click)
        except Exception: pass
        self.sh.palette = None; self.destroy(); self.sh.restore_focus()


def shortcuts_sheet(sh):
    """Modal list of all keyboard shortcuts."""
    ctx = sh.ctx; P = ctx.P
    from .dialogs import Dialog
    d = tk.Toplevel(ctx.root); d.title("Keyboard shortcuts"); d.configure(bg=P["card"]); d.transient(ctx.root); d.resizable(False, False)
    tk.Label(d, text="Keyboard shortcuts", bg=P["card"], fg=P["text"], font=ctx.f_title).pack(anchor="w", padx=24, pady=(18, 8))
    grid = tk.Frame(d, bg=P["card"]); grid.pack(padx=24)
    rows = [(c.group, c.title, c.keys) for c in sh.commands if c.keys] + [("Files", "Open / Save dialog: back / forward / up", "Alt+← / Alt+→ / Alt+↑"),
            ("Files", "Search / rename / hidden files / path", "Ctrl+F / F2 / Ctrl+H / Ctrl+L"), ("Menus", "Open File / Download / View menu", "Alt+F / Alt+D / Alt+V"),
            ("General", "Move between controls", "Tab / Shift+Tab"), ("General", "Press the focused button or switch", "Enter / Space")]
    for i, (g, t, k) in enumerate(rows):
        tk.Label(grid, text=g, bg=P["card"], fg=P["muted"], font=ctx.f_small, anchor="w", width=10).grid(row=i, column=0, sticky="w", pady=2)
        tk.Label(grid, text=t, bg=P["card"], fg=P["text"], font=ctx.f_body, anchor="w").grid(row=i, column=1, sticky="w", padx=(6, 28))
        tk.Label(grid, text=k, bg=P["soft"], fg=P["text"], font=ctx.f_small, padx=8, pady=1).grid(row=i, column=2, sticky="e", pady=2)
    row = tk.Frame(d, bg=P["card"]); row.pack(fill="x", padx=24, pady=16); b = Btn(ctx, row, "Close", d.destroy, "primary"); b.pack(side="right")
    d.bind("<Escape>", lambda e: d.destroy()); d.bind("<Return>", lambda e: d.destroy()); b.focus_set()
    d.update_idletasks(); r = ctx.root
    d.geometry(f"+{r.winfo_rootx() + max(0, (r.winfo_width() - d.winfo_width()) // 2)}+{r.winfo_rooty() + 50}")
    try: d.grab_set()
    except tk.TclError: pass
