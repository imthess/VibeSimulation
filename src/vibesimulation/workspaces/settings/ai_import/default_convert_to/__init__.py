"""Setting: the tab a picture becomes by default (idea 6: choose it yourself instead of Auto, which makes the AI spend tokens deciding)."""
from tkinter import ttk
import tkinter as tk
from vibesimulation.workspaces.ai_import.core.prompt import LABELS, TARGETS
from vibesimulation.workspaces.settings.item import D
def item(page):
    ctx = page.ctx
    def make(parent):
        names = [LABELS[t] for t in TARGETS]; v = tk.StringVar(value=LABELS.get(ctx.cfg.get("import_target", "auto"), names[0]))
        cb = ttk.Combobox(parent, textvariable=v, values=names, state="readonly", style="Modern.TCombobox", width=26)
        def chosen(e=None):
            key = TARGETS[names.index(v.get())]; ctx.cfg["import_target"] = key; ctx.save_cfg()
            try:
                view = page.shell.pages["import"].view; view.target.set(LABELS[key]); view.target_changed()
            except Exception: pass
        cb.bind("<<ComboboxSelected>>", chosen)
        page.setters["import_target"] = lambda: v.set(LABELS.get(ctx.cfg.get("import_target", "auto"), names[0]))
        return cb
    return D("AI & Import", "Convert pictures to", "Pick the tab yourself. \"Auto\" makes the AI decide between a logic and an analog circuit, which costs a longer instruction and extra thinking.", make)
