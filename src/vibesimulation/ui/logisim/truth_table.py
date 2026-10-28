"""Box 4: truth table (inputs | intermediate signals | outputs)."""
import tkinter as tk
from tkinter import ttk

from ...core.bits import fmt
from ..theme import auto
from ..widgets import Btn
from ..views.base import View



def ctx_bits(view):
    return view.ctx.cfg.get("table_bits", MAX_TABLE_BITS)


class TableView(View):
    number, title, hint = None, "Truth table", ""

    def build(self):
        ctx = self.ctx
        b = self.body; b.rowconfigure(0, weight=1)
        self.show_mid = tk.BooleanVar(value=ctx.cfg.get("show_mid", True))
        box = tk.Frame(b, bd=0); box.grid(row=0, column=0, sticky="nsew"); box.columnconfigure(0, weight=1); box.rowconfigure(0, weight=1)
        self.box = box
        self.tree = ttk.Treeview(box, show="headings", selectmode="browse", style="Modern.Treeview")
        sy = ttk.Scrollbar(box, command=self.tree.yview, style="Thin.Vertical.TScrollbar")
        sx = ttk.Scrollbar(box, orient="horizontal", command=self.tree.xview, style="Thin.Horizontal.TScrollbar")
        self.tree.configure(yscrollcommand=auto(sy), xscrollcommand=auto(sx))
        self.tree.grid(row=0, column=0, sticky="nsew"); sy.grid(row=0, column=1, sticky="ns"); sx.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._on_row)
        bot = tk.Frame(b, bd=0); bot.grid(row=1, column=0, sticky="ew", pady=(6, 0)); self.bot = bot
        ttk.Checkbutton(bot, text="Show intermediate outputs", variable=self.show_mid, command=self.rebuild, style="Card.TCheckbutton").pack(side="right")
        self.status = tk.Label(bot, text="", font=ctx.f_small); self.status.pack(side="left")
        self.btn_copy = Btn(ctx, self.tools, "⧉", self.copy, "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Copy truth table"); self.btn_copy.pack(side="right", padx=(6, 0))
        self.playing = self.repeat = False; self.pos = 0; self._job = None
        self.btn_rep = Btn(ctx, self.tools, "⟳", self.toggle_repeat, "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Repeat: start again from the first row after the last one"); self.btn_rep.pack(side="right")
        self.btn_play = Btn(ctx, self.tools, "▶", self.toggle_play, "ghost", padx=9, pady=0, font=ctx.f_icon).tip("Play: test every row of the truth table one after another"); self.btn_play.pack(side="right")
        self.data = None            # (header texts, rows of texts) of what is shown
        self.groups = (0, 0, 0)     # input / intermediate / output column counts shown
        self._syncing = False
        ctx.themed.append(self._paint); self._paint()

    def _paint(self):
        P = self.ctx.P
        self.box.configure(bg=P["card"]); self.bot.configure(bg=P["card"]); self.status.configure(bg=P["card"], fg=P["muted"])
        self.tree.tag_configure("odd", background=P["field"])

    def on_doc(self, kind):
        if kind == "changed": self.rebuild()
        elif kind == "values": self.sync_row()

    # ---- play / repeat: step through every row, one every few seconds (Settings > Logisim)
    def interval(self):
        try: return max(0.2, float(self.ctx.cfg.get("play_secs", 2)))
        except (TypeError, ValueError): return 2.0

    def n_rows(self): return len(self.data[1]) if self.data else 0

    def toggle_repeat(self):
        self.repeat = not self.repeat; self.btn_rep.kind = "tonal" if self.repeat else "ghost"; self.btn_rep.paint()
        self.status.config(text="Repeat on: after the last row it starts again from the first." if self.repeat else "Repeat off.")

    def toggle_play(self):
        if self.playing: self.stop("Stopped.")
        elif self.n_rows():
            self.playing = True; self.pos = 0; self.btn_play.text = "⏸"; self.btn_play.kind = "tonal"; self.btn_play.paint(); self.step()
        else: self.status.config(text="Nothing to play: the circuit has no truth table.")

    def stop(self, msg=None):
        if self._job: self.ctx.root.after_cancel(self._job); self._job = None
        self.playing = False; self.btn_play.text = "▶"; self.btn_play.kind = "ghost"
        try: self.btn_play.paint()
        except tk.TclError: pass
        if msg: self.status.config(text=msg)

    def step(self):
        self._job = None
        if not self.playing: return
        n = self.n_rows()
        if not n or not self.doc.valid: self.stop(); return
        if self.pos >= n:
            if not self.repeat: self.stop("Finished: all rows tested."); return
            self.pos = 0
        self.apply_row(self.pos)
        self.status.config(text=f"Row {self.pos + 1} of {n} · every {self.interval():g} s" + (" · repeat" if self.repeat else ""))
        self.pos += 1
        self._job = self.ctx.root.after(int(self.interval() * 1000), self.step)

    def apply_row(self, k):
        vals = {}
        for p in reversed(self.doc.circuit.inputs):
            vals[p.name] = k & ((1 << p.width) - 1); k >>= p.width
        self.doc.set_inputs(vals)

    def rebuild(self):
        if self.playing: self.stop()
        tr = self.tree; tr.delete(*tr.get_children())
        d = self.doc
        if not d.valid:
            self.data = None; self.btn_play.set_enabled(False); return
        c = d.circuit
        limit = self.ctx.cfg.get("table_bits", 12)
        td = c.table(limit)
        if td is None:
            tr.configure(columns=()); self.data = None
            if d.has_seq(): self.status.config(text="This circuit remembers things (flip-flops, counters ...), so it has no truth table. Use Tick / the clock in the circuit view.")
            else: self.status.config(text=f"Truth table is limited to {limit} input bits (this circuit has {sum(p.width for p in c.inputs)}).")
            self.btn_copy.set_enabled(False); self.btn_play.set_enabled(False); return
        ins, mids, outs, rows = td
        widths = c.signals()
        n_in, n_mid = len(ins), len(mids)
        show_mid = self.show_mid.get() and bool(mids)
        cols, heads, idx = [], [], []
        def add(names, start, sep):
            if sep and cols: cols.append(f"s{len(cols)}"); heads.append(""); idx.append(None)
            for k, n in enumerate(names): cols.append(f"c{len(cols)}"); heads.append(n); idx.append(start + k)
        add(ins, 0, False)
        if show_mid: add(mids, n_in, True)
        add(outs, n_in + n_mid, True)
        names_all = ins + mids + outs
        tr.configure(columns=cols)
        for cid, h, i in zip(cols, heads, idx):
            w = 14 if i is None else max(52, 16 + 8 * max(len(h), widths.get(h, 1)))
            tr.heading(cid, text=h); tr.column(cid, width=w, minwidth=14 if i is None else 40, anchor="center", stretch=False)
        for r, row in enumerate(rows):
            tr.insert("", "end", iid=f"r{r}", values=["" if i is None else fmt(row[i], widths.get(names_all[i], 1)) for i in idx], tags=("odd",) if r % 2 else ())
        self.groups = (n_in, n_mid if show_mid else 0, len(outs))
        shown = [i for i in idx if i is not None]
        self.data = ([names_all[i] for i in shown], [[fmt(row[i], widths.get(names_all[i], 1)) for i in shown] for row in rows])
        self.status.config(text=f"{len(rows)} rows   ·   inputs {'· intermediate ' if show_mid else ''}· outputs")
        self.btn_copy.set_enabled(True); self.btn_play.set_enabled(True)
        self.sync_row()

    # ---- rows <-> input values (first input is the most significant, like the table order)
    def row_of(self):
        k = 0
        for p in self.doc.circuit.inputs:
            k = (k << p.width) | (self.doc.invals.get(p.name, 0) & ((1 << p.width) - 1))
        return k

    def sync_row(self):
        if not self.data or not self.doc.valid: return
        iid = f"r{self.row_of()}"
        if self.tree.exists(iid):
            self._syncing = True
            try: self.tree.selection_set(iid); self.tree.see(iid)
            finally: self.ctx.root.after(60, lambda: setattr(self, "_syncing", False))

    def _on_row(self, _e=None):
        if self._syncing or not self.doc.valid or not self.data: return
        s = self.tree.selection()
        if not s: return
        k = int(s[0][1:])
        if self.playing: self.pos = k + 1          # clicking a row while playing: carry on from there
        self.apply_row(k)

    def copy(self):
        if not self.data: return
        names, rows = self.data
        self.ctx.root.clipboard_clear(); self.ctx.root.clipboard_append("\n".join(["\t".join(names)] + ["\t".join(r) for r in rows]) + "\n"); self.ctx.root.update()
        self.status.config(text="Truth table copied. Paste it into Excel, Sheets or a document.")
