"""Import & AI page: the picture box with the AI model settings, full width."""
import tkinter as tk

from .import_view import ImportView


class ImportPage(tk.Frame):
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.shell = ctx, shell
        self.view = ImportView(ctx, shell.doc, self)
        self.view.card.pack(fill="both", expand=True, padx=40, pady=(24, 40))
        self.view.main = shell
        ctx.themed.append(lambda: self.configure(bg=ctx.P["bg"])); self.configure(bg=ctx.P["bg"])
