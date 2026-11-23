"""Import & AI page: the picture box with the AI model settings, full width."""
import tkinter as tk

from vibesimulation.workspaces.ai_import.ui.import_view import ImportView
from vibesimulation.workspaces.ai_import.ui.skin import tokens
class ImportPage(tk.Frame):
    def __init__(self, ctx, master, shell):
        super().__init__(master, bd=0); self.ctx, self.shell = ctx, shell
        self.view = ImportView(ctx, shell.doc, self)
        self.view.card.pack(fill="both", expand=True, padx=6, pady=(2, 5))
        self.view.main = shell
        ctx.themed.append(lambda: self.configure(bg=tokens(ctx)["bg"])); self.configure(bg=tokens(ctx)["bg"])
