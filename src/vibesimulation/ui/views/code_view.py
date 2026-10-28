"""A text-editor box with line numbers, red error lines, a status strip and debounced typing (Template Method).

Shared by the Logisim JSON box and the VLSI Verilog box. A subclass says
- ``flush_text(text)`` what to do with the text once typing pauses,
- ``on_doc(kind)``   how to show the Document's state in the editor,
and may add its own tool buttons in ``extra_tools()`` and colours in ``paint_extra()``.
"""
import tkinter as tk
from tkinter import ttk

from ..theme import auto
from ..widgets import Btn, Notice
from .base import View


class CodeView(View):
    DELAY = 150                 # ms of quiet before typed text is handed to flush()
    NAME = "Text"               # what the copy button says it copied

    def build(self):
        ctx = self.ctx
        self.main = None            # set by the main window (undo/redo go through it)
        self._timer = None
        self.err_lines = set()
        Btn(ctx, self.tools, "⧉", self.copy, "ghost", padx=9, pady=0, font=ctx.f_icon).tip(f"Copy {self.NAME}").pack(side="right")
        self.b_redo = Btn(ctx, self.tools, "↷", lambda: self.main.redo(), "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Redo (Ctrl+Y)")
        self.b_undo = Btn(ctx, self.tools, "↶", lambda: self.main.undo(), "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Undo (Ctrl+Z)")
        self.b_redo.pack(side="right"); self.b_undo.pack(side="right")
        self.extra_tools()
        self._build_editor()
        ctx.themed.append(self._paint); self._paint()

    # ---- hooks for subclasses
    def extra_tools(self): pass

    def paint_extra(self): pass

    # ---- widgets
    def _build_editor(self):
        ctx = self.ctx; b = self.body; b.rowconfigure(0, weight=1)
        box = tk.Frame(b, bd=0); box.grid(row=0, column=0, sticky="nsew"); box.columnconfigure(1, weight=1); box.rowconfigure(0, weight=1)
        self.box = box
        self.txt = tk.Text(box, wrap="none", undo=False, font=ctx.f_mono, height=6, bd=0, highlightthickness=0, padx=12, pady=10, relief="flat")
        self.gut = tk.Canvas(box, bd=0, highlightthickness=0, width=40, cursor="arrow"); self.gut.grid(row=0, column=0, sticky="ns")
        sy = ttk.Scrollbar(box, command=self.txt.yview, style="Thin.Vertical.TScrollbar")
        sx = ttk.Scrollbar(box, orient="horizontal", command=self.txt.xview, style="Thin.Horizontal.TScrollbar")
        asy = auto(sy)
        self.txt.configure(yscrollcommand=lambda a, b: (asy(a, b), self._gutter()), xscrollcommand=auto(sx))
        self.txt.grid(row=0, column=1, sticky="nsew"); sy.grid(row=0, column=2, sticky="ns"); sx.grid(row=1, column=1, sticky="ew")
        self.txt.bind("<Configure>", lambda e: self._gutter()); self.txt.bind("<KeyRelease>", lambda e: self._gutter()); self.txt.bind("<ButtonRelease-1>", lambda e: self._gutter())
        self.gut.bind("<Button-1>", self._gutter_click)
        self.txt.bind("<<Modified>>", self._modified)
        t = self.txt
        for mod in ("Control", "Command"):                      # undo / redo go to the Document (one history for every box)
            for key in ("z", "y", "Y", "Z"):
                fn = (lambda e: self.main.undo()) if key == "z" else (lambda e: self.main.redo())
                try: t.bind(f"<{mod}-Key-{key}>", lambda e, fn=fn: (fn(e), "break")[1])
                except tk.TclError: pass
        t.bind("<Control-Key-a>", lambda e: (t.tag_add("sel", "1.0", "end-1c"), "break")[1])
        t.bind("<Control-Key-A>", lambda e: (t.tag_add("sel", "1.0", "end-1c"), "break")[1])
        t.bind("<<Paste>>", self._paste)
        self.status = Notice(ctx, b, height=2); self.status.grid(row=1, column=0, sticky="ew", pady=(6, 0))

    def _paint(self):
        P = self.ctx.P
        self.box.configure(bg=P["card"])
        self.txt.configure(bg=P["field"], fg=P["text"], insertbackground=P["text"], selectbackground=P["sel"], selectforeground=P["text"])
        self.txt.tag_configure("errline", background=P["badbg"])
        self.paint_extra()
        self.txt.tag_raise("sel")
        self.gut.configure(bg=P["field"]); self._gutter()

    # ---- line numbers and error lines (like a code editor)
    def _gutter(self):
        g, t, P = self.gut, self.txt, self.ctx.P
        try:
            n = int(t.index("end-1c").split(".")[0]); f = self.ctx.f_mono
            w = f.measure("0") * max(2, len(str(n))) + 22
            if int(g["width"]) != w: g.configure(width=w)
            g.delete("all"); g.create_line(w - 1, 0, w - 1, g.winfo_height(), fill=P["border"])
            cur = int(t.index("insert").split(".")[0]); idx = t.index("@0,0")
            while True:
                d = t.dlineinfo(idx)
                if d is None: break
                ln = int(idx.split(".")[0]); y = d[1] + d[3] // 2; bad = ln in self.err_lines
                if bad: g.create_rectangle(0, d[1], w - 1, d[1] + d[3], fill=P["badbg"], outline=""); g.create_rectangle(0, d[1], 3, d[1] + d[3], fill=P["bad"], outline="")
                g.create_text(w - 10, y, text=str(ln), anchor="e", font=f, fill=P["bad"] if bad else (P["text"] if ln == cur else P["muted"]))
                nxt = t.index(f"{idx}+1line")
                if nxt == idx or int(nxt.split(".")[0]) > n: break
                idx = nxt
        except tk.TclError: pass

    def _gutter_click(self, e):
        d = self.txt.dlineinfo(self.txt.index(f"@0,{e.y}"))
        if d is not None: self.txt.mark_set("insert", self.txt.index(f"@0,{e.y}")); self.txt.focus_set(); self._gutter()

    def mark_lines(self, lines):
        """Paint the given (1-based) lines red."""
        self.txt.tag_remove("errline", "1.0", "end"); self.err_lines = set(lines)
        n = int(self.txt.index("end-1c").split(".")[0])
        for ln in self.err_lines:
            if 1 <= ln <= n: self.txt.tag_add("errline", f"{ln}.0", f"{ln}.0 lineend+1c")
        self.txt.tag_lower("errline"); self._gutter()

    # ---- typing -> flush() after a short pause
    def _modified(self, _e=None):
        if self.txt.edit_modified():
            self.txt.edit_modified(False)
            if self._timer: self.ctx.root.after_cancel(self._timer)
            self._timer = self.ctx.root.after(self.DELAY, self._due)
            self.on_typed()

    def on_typed(self): pass

    def _due(self):
        self.flush_now()

    def flush(self):
        """Hand pending typed text over right away (the shell calls this before undo / save so nothing typed is lost)."""
        if self._timer:
            self.ctx.root.after_cancel(self._timer); self._timer = None
            self.flush_text(self.get_text())

    flush_now = flush

    def flush_text(self, text):
        """The typed text, after a pause (subclass: give it to the Document)."""
        raise NotImplementedError

    def get_text(self): return self.txt.get("1.0", "end").rstrip("\n")

    def show_text(self, text):
        """Replace what the editor shows, keeping the scroll position."""
        y = self.txt.yview()[0]
        self.txt.delete("1.0", "end"); self.txt.insert("1.0", text); self.txt.yview_moveto(y); self.txt.edit_modified(False)

    def _paste(self, _e):
        try: s = self.ctx.root.clipboard_get()
        except tk.TclError: return "break"
        if self.txt.tag_ranges("sel"): self.txt.delete("sel.first", "sel.last")
        self.txt.insert("insert", s); self.txt.see("insert"); return "break"

    def copy(self):
        self.ctx.root.clipboard_clear(); self.ctx.root.clipboard_append(self.txt.get("1.0", "end").strip() + "\n"); self.ctx.root.update()
        self.status.set(f"{self.NAME} copied to the clipboard.", "info")
