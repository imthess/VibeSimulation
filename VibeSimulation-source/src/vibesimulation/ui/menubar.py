"""The top menu bar, laid out like VS Code's: File, Edit, ... View, ... Help in one slim row, with a command-search box in the middle.

Which menus appear depends on the page: the Logisim workspace gets Logisim's own menus (Project, Simulate), the Multisim workspace gets
Multisim's (Place, Simulate, Transfer, Tools). Alt+F / Alt+E / Alt+V ... open them from the keyboard."""
import time
import tkinter as tk

from . import menus


class MenuBar(tk.Frame):
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.shell = ctx, shell
        self.logo = tk.Label(self, text="◈", font=ctx.f_icon); self.logo.pack(side="left", padx=(14, 8), pady=4)
        self.row = tk.Frame(self, bd=0); self.row.pack(side="left")
        self.theme = tk.Label(self, text="◐", font=ctx.f_icon, cursor="hand2", padx=10); self.theme.pack(side="right", padx=(0, 6))
        self.theme.bind("<Button-1>", lambda e: shell.toggle_dark())
        self.pill = tk.Label(self, text="", font=ctx.f_small, cursor="hand2", padx=12, pady=3, anchor="center", width=38)
        self.pill.place(relx=1.0, x=-52, rely=0.5, anchor="e"); self.pill.bind("<Button-1>", lambda e: shell.open_palette())
        self.buttons, self.page, self.title = [], "home", "Home"
        self.line = tk.Frame(master, height=1, bd=0)
        ctx.themed.append(self._paint); self.rebuild(); self._paint()

    # ---- the labels
    def rebuild(self):
        for b in self.buttons: b.destroy()
        self.buttons = []
        for name, builder in menus.menus_for(self.shell, self.page):
            b = tk.Label(self.row, text=name, font=self.ctx.f_body, padx=10, pady=5, cursor="arrow"); b.name = name; b.builder = builder
            b.bind("<ButtonRelease-1>", lambda e, b=b: self.popup(b)); b.bind("<Enter>", lambda e, b=b: self._hot(b, True)); b.bind("<Leave>", lambda e, b=b: self._hot(b, False))
            b.bind("<Return>", lambda e, b=b: self.popup(b)); b.bind("<Down>", lambda e, b=b: self.popup(b)); b.bind("<Right>", lambda e, b=b: self.hop(b, 1)); b.bind("<Left>", lambda e, b=b: self.hop(b, -1))
            b.configure(takefocus=1); b.pack(side="left"); self.buttons.append(b)
        self._paint()

    def cmd(self): pass

    def set_page(self, name, title):
        changed = name != self.page
        self.page, self.title = name, title
        if changed: self.rebuild()
        self.pill.configure(text=f"⌕   {title}  —  search commands   (Ctrl+K)")

    def _hot(self, b, on):
        P = self.ctx.P; b.configure(bg=P["soft"] if on else P["card"])

    def _paint(self):
        P = self.ctx.P
        for w in (self, self.row): w.configure(bg=P["card"])
        self.logo.configure(bg=P["card"], fg=P["accent"]); self.theme.configure(bg=P["card"], fg=P["muted"])
        self.pill.configure(bg=P["soft"], fg=P["muted"]); self.line.configure(bg=P["border"])
        for b in self.buttons: b.configure(bg=P["card"], fg=P["text"])

    def hop(self, b, d):
        i = self.buttons.index(b) + d
        if 0 <= i < len(self.buttons): self.buttons[i].focus_set()
        return "break"

    def open_label(self, name):
        for b in self.buttons:
            if b.name == name: b.focus_set(); self.popup(b); return True
        return False

    def open_index(self, i):
        if 0 <= i < len(self.buttons): self.buttons[i].focus_set(); self.popup(self.buttons[i])

    def acc(self, title):
        for c in self.shell.commands:
            if c.title == title: return c.keys
        return ""

    def popup(self, btn):
        pc = self.ctx.popup_closed
        if pc and time.time() - pc[0] < 0.4 and pc[1] is btn:      # clicking the label of an open menu closes it
            self.ctx.popup_closed = None; return
        m = self.ctx.menu(); btn.builder(m); self._hot(btn, True)
        try: m.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
        finally: self.after(10, lambda: self._hot(btn, False))

    # ---- kept for callers that build one menu directly
    def file_menu(self, m): menus.file_menu(self.shell, m)
    def download_menu(self, m): menus.export_menu(self.shell, m)
    def view_menu(self, m): menus.view_menu(self.shell, m)
