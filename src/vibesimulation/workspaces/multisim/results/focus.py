"""'Show results for': pick which parts and nets every Multisim result view reports.

`Focus` holds the choice (nothing chosen = everything); `FocusPicker` is the small button + popup that edits it.
A chosen part brings in the nets it touches, so picking R2 shows R2's voltage, current and power plus the voltages at its two ends."""
import tkinter as tk

from ..engine.solver import is_ground


class Focus:
    def __init__(self, doc):
        self.doc, self.parts, self.extra, self.listeners = doc, set(), set(), []

    @property
    def active(self): return bool(self.parts or self.extra)

    def clear(self): self.set(set(), set())

    def set(self, parts, nets):
        self.parts, self.extra = set(parts), set(nets); self.prune(); self.fire()

    def prune(self):
        nl = self.doc.netlist
        if nl is None: return
        ids = {p.id for p in nl.parts}; self.parts &= ids; self.extra &= {str(n) for n in nl.nets()}

    def fire(self):
        for f in list(self.listeners): f()

    def nets(self):
        """Every net in scope: the chosen nets plus those the chosen parts touch."""
        nl = self.doc.netlist; out = set(self.extra)
        if nl is not None:
            for p in nl.parts:
                if p.id in self.parts: out |= {str(n).strip() for n in list(p.nodes) + list(p.control_nodes()) if not is_ground(n)}
        return out

    def allows_part(self, pid): return not self.active or pid in self.parts

    def allows_net(self, net): return not self.active or str(net) in self.nets()

    def allows_probe(self, name):
        """'V(n1)', 'I(R1)', 'I(Q1.C)', 'Z(V1)' -> is it in scope?"""
        if not self.active: return True
        kind, _, rest = name.partition("("); body = rest.rstrip(")")
        if kind == "V": return self.allows_net(body)
        return body.split(".")[0] in self.parts

    def label(self):
        if not self.active: return "All parts and nets"
        names = sorted(self.parts) + sorted(self.extra - self.nets_of_parts())
        return ", ".join(names) if len(", ".join(names)) <= 26 else f"{len(names)} selected"

    def nets_of_parts(self):
        keep = self.extra; self.extra = set()
        try: return self.nets()
        finally: self.extra = keep


class FocusPicker(tk.Frame):
    """A button showing the current choice; clicking opens a popup with a part list and a net list."""

    def __init__(self, ctx, master, focus):
        super().__init__(master, bd=0); self.ctx, self.focus, self.pop = ctx, focus, None
        self.lbl = tk.Label(self, text="Show results for", font=ctx.f_small); self.lbl.pack(side="left")
        from ....ui.widgets import Btn
        self.btn = Btn(ctx, self, "All parts and nets  ▾", self.toggle, "secondary", pady=2, padx=10, font=ctx.f_small); self.btn.pack(side="left", padx=8)
        self.btn.tip("Choose the parts and nets whose voltage, current and power are shown")
        focus.listeners.append(self.sync); ctx.themed.append(self._paint); self._paint()

    def _paint(self):
        P = self.ctx.P; self.configure(bg=P["card"]); self.lbl.configure(bg=P["card"], fg=P["muted"])

    def sync(self):
        try: self.btn.config(text=self.focus.label() + "  ▾")
        except tk.TclError: pass

    def toggle(self):
        if self.pop is not None and self.pop.winfo_exists(): self.close(); return
        nl = self.focus.doc.netlist
        if nl is None or not self.focus.doc.valid: return
        P, ctx = self.ctx.P, self.ctx
        self.pop = pop = tk.Toplevel(self); pop.transient(self.winfo_toplevel()); pop.title("Show results for"); pop.configure(bg=P["card"])
        pop.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() + 4}"); pop.bind("<Escape>", lambda e: self.close())
        tk.Label(pop, text="Click parts or nets to switch them on or off, as many as you like. The nets of a chosen part come along.", font=ctx.f_small, bg=P["card"], fg=P["muted"]).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))
        def box(col, title, items):
            f = tk.Frame(pop, bg=P["card"]); f.grid(row=2, column=col, padx=10, pady=4, sticky="nsew")
            tk.Label(pop, text=title, font=ctx.f_bold, bg=P["card"], fg=P["text"]).grid(row=1, column=col, sticky="w", padx=10)
            lb = tk.Listbox(f, selectmode="multiple", height=min(12, max(4, len(items))), exportselection=False, bd=0, highlightthickness=1, font=ctx.f_small, width=22,
                            bg=P["field"], fg=P["text"], selectbackground=P["accent"], selectforeground=P["accent_fg"], highlightbackground=P["border"], highlightcolor=P["accent"])
            for t in items: lb.insert("end", t)
            lb.pack(fill="both", expand=True); lb.bind("<<ListboxSelect>>", lambda e: self.apply()); return lb
        self.pids = [p.id for p in nl.parts]; self.nids = [str(n) for n in nl.nets()]
        self.lp = box(0, "Parts", [f"{p.id}  ({p.type_name})" for p in nl.parts]); self.ln = box(1, "Nets", self.nids)
        for i, pid in enumerate(self.pids):
            if pid in self.focus.parts: self.lp.selection_set(i)
        for i, n in enumerate(self.nids):
            if n in self.focus.extra: self.ln.selection_set(i)
        row = tk.Frame(pop, bg=P["card"]); row.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 10))
        from ....ui.widgets import Btn
        Btn(ctx, row, "Show everything", self.everything, "ghost", pady=2, padx=10, font=ctx.f_small).pack(side="left")
        Btn(ctx, row, "Done", self.close, "primary", pady=2, padx=14, font=ctx.f_small).pack(side="right")
        pop.grid_columnconfigure(0, weight=1); pop.grid_columnconfigure(1, weight=1); pop.focus_set()

    def apply(self):
        self.focus.set({self.pids[i] for i in self.lp.curselection()}, {self.nids[i] for i in self.ln.curselection()})

    def everything(self):
        self.lp.selection_clear(0, "end"); self.ln.selection_clear(0, "end"); self.focus.clear()

    def close(self):
        if self.pop is not None and self.pop.winfo_exists(): self.pop.destroy()
        self.pop = None
