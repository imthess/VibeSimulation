"""A themed modal window (Template Method: subclasses fill ``build(body)``)."""
import tkinter as tk


class Box(tk.Toplevel):
    def __init__(self, ctx, title, width=560, height=None):
        super().__init__(ctx.root); self.ctx = ctx; P = ctx.P
        self.title(title); self.configure(bg=P["card"]); self.transient(ctx.root)
        self.body = tk.Frame(self, bg=P["card"]); self.body.pack(fill="both", expand=True, padx=22, pady=18)
        self.build(self.body)
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        w = max(width, self.winfo_reqwidth()); h = height or self.winfo_reqheight(); r = ctx.root
        self.geometry(f"{w}x{h}+{r.winfo_rootx() + max(0, (r.winfo_width() - w) // 2)}+{r.winfo_rooty() + max(0, (r.winfo_height() - h) // 4)}")
        try: self.grab_set()
        except tk.TclError: pass

    def build(self, body): raise NotImplementedError

    # small helpers
    def label(self, parent, text, kind="body", **kw):
        P = self.ctx.P; f = {"title": self.ctx.f_title, "small": self.ctx.f_small, "body": self.ctx.f_body}[kind]
        fg = P["muted"] if kind == "small" else P["text"]
        l = tk.Label(parent, text=text, bg=P["card"], fg=kw.pop("fg", fg), font=f, anchor="w", justify="left", **kw); return l
