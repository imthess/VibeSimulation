"""A strip of tabs above the Logisim panes: every circuit you have opened stays one click away.

The project (Document) already keeps all its circuits; the tabs are just the ones you chose to keep open.  Clicking a tab edits
that circuit (the circuit, JSON and truth table panes all follow); x closes the tab (the circuit stays in the project and in the
explorer); + makes a new circuit.  Right-click a tab to rename, close or delete it.
"""
import tkinter as tk


class CircuitTabs(tk.Frame):
    def __init__(self, ctx, master, doc, circuit_view):
        super().__init__(master, bd=0)
        self.ctx, self.doc, self.cv = ctx, doc, circuit_view
        self.open = [doc.cur]
        self.known = list(doc.circuit_names())
        self.items = {}
        self.plus = tk.Label(self, text="+", font=ctx.f_bold, cursor="hand2", padx=10)
        self.plus.bind("<Button-1>", lambda e: self.cv.new_circuit())
        self.plus.bind("<Enter>", lambda e: self.plus.configure(fg=self.ctx.P["text"])); self.plus.bind("<Leave>", lambda e: self.plus.configure(fg=self.ctx.P["muted"]))
        ctx.themed.append(self.paint)
        doc.subscribe(self.on_doc)
        self.rebuild()

    # ---- keeping the list of open tabs in step with the project
    def on_doc(self, kind):
        if kind != "circuits": return
        names = list(self.doc.circuit_names())
        gone = [n for n in self.known if n not in names]; new = [n for n in names if n not in self.known]
        if len(gone) == 1 and len(new) == 1:                       # one name replaced by another = a rename
            self.open = [new[0] if n == gone[0] else n for n in self.open]
        else:
            self.open = [n for n in self.open if n in names]
        if self.doc.cur not in self.open: self.open.append(self.doc.cur)
        self.known = names
        self.rebuild()

    def rebuild(self):
        for w in list(self.winfo_children()):
            if w is not self.plus: w.destroy()
        self.items = {}
        for n in self.open:
            f = tk.Frame(self, bd=0, cursor="hand2")
            lab = tk.Label(f, text=n, font=self.ctx.f_body, padx=10, pady=5)
            x = tk.Label(f, text="×", font=self.ctx.f_bold, padx=6, cursor="hand2")
            lab.pack(side="left"); x.pack(side="left")
            for w in (f, lab): w.bind("<Button-1>", lambda e, n=n: self.pick(n)); w.bind("<Button-3>", lambda e, n=n: self.menu(e, n)); w.bind("<Button-2>", lambda e, n=n: self.close(n))
            x.bind("<Button-1>", lambda e, n=n: self.close(n))
            f.pack(side="left", padx=(0, 2))
            self.items[n] = (f, lab, x)
        self.plus.pack_forget(); self.plus.pack(side="left")
        self.paint()

    def paint(self):
        P = self.ctx.P
        try:
            self.configure(bg=P["bg"])
            for n, (f, lab, x) in self.items.items():
                on = n == self.doc.cur
                bg = P["card"] if on else P["soft"]
                f.configure(bg=bg, highlightthickness=0)
                lab.configure(bg=bg, fg=P["text"] if on else P["muted"], font=self.ctx.f_bold if on else self.ctx.f_body)
                x.configure(bg=bg, fg=P["muted"])
            self.plus.configure(bg=P["bg"], fg=P["muted"])
        except tk.TclError: pass

    # ---- actions
    def pick(self, name):
        if name != self.doc.cur:
            self.doc.switch(name)
        self.paint()

    def close(self, name):
        if len(self.open) <= 1: return                              # one circuit always stays open
        i = self.open.index(name); self.open.remove(name)
        if name == self.doc.cur: self.doc.switch(self.open[min(i, len(self.open) - 1)])
        self.rebuild()

    def menu(self, e, name):
        m = self.ctx.menu()
        m.add_command(label="Rename…", command=lambda: self.cv.rename_circuit(name))
        m.add_command(label="Close tab", command=lambda: self.close(name), state="normal" if len(self.open) > 1 else "disabled")
        m.add_command(label="Close other tabs", command=lambda: self.close_others(name), state="normal" if len(self.open) > 1 else "disabled")
        m.add_separator()
        m.add_command(label="Delete circuit…", command=lambda: self.cv.delete_circuit(name), state="normal" if len(self.doc.circuit_names()) > 1 else "disabled")
        m.tk_popup(e.x_root, e.y_root)

    def close_others(self, name):
        self.open = [name]
        if self.doc.cur != name: self.doc.switch(name)
        self.rebuild()
