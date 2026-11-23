"""Setting: a different AI for the AI button than for picture import (e.g. a local model for the button, a strong cloud model for pictures)."""
import tkinter as tk

from vibesimulation.ui.controls.widgets import Btn, Switch
from vibesimulation.workspaces.ai_import.core import autodetect, profile
from vibesimulation.workspaces.ai_import.core.key_detect import clean_key, detect_provider
from vibesimulation.workspaces.ai_import.core.providers import PROVIDERS
from vibesimulation.workspaces.settings.item import D

AUTO = "Detect from the key"


def _setup(page, label):
    ctx = page.ctx; cur_p, cur_m, cur_b = profile.get(ctx.cfg)
    names = [AUTO] + list(PROVIDERS)
    def check(v):
        key = clean_key(v["key"]); name = v["provider"]
        if name == AUTO:
            name = detect_provider(key) if key else None
            if not name: return "The key's service could not be recognised: choose the provider in the list."
        prov = PROVIDERS[name]; v["provider"] = name
        if prov.env and not key and not profile.key(name, prov.env): return f"{name} needs an API key. Paste it above.\n{prov.help}"
        if not v["model"]:
            if prov.local: v["model"] = prov.models[0]
            else:
                found = autodetect.discover(key or profile.key(name, prov.env), name, {name: v["base"]} if v["base"] else None, PROVIDERS)
                if found.accepted is False: return found.message
                v["model"] = found.best or prov.models[0]
        if not v["base"] and prov.local: v["base"] = prov.base
        return None
    r = ctx.ask_form("AI for the AI button", "Used only by the AI button. Picture import keeps the service chosen on the Import & AI page. Leave the model empty to pick the best one automatically.",
                     [("provider", "Service", cur_p if cur_p else AUTO, names), ("key", "API key (not needed for Ollama)", "", None), ("model", "Model (optional)", cur_m, None), ("base", "Server address (Ollama / custom)", cur_b, None)], check)
    if not r: return None
    note = profile.save(ctx.cfg, r["provider"], r["model"], r["base"], r["key"], PROVIDERS); ctx.save_cfg()
    return note


def item(page):
    ctx = page.ctx

    def make(parent):
        f = tk.Frame(parent, bd=0, bg=parent.cget("bg")); v = tk.BooleanVar(value=bool(ctx.cfg.get("ai_sep_on", False)))
        info = tk.Label(f, text=profile.describe(ctx.cfg), font=ctx.f_small, bg=parent.cget("bg"), fg=ctx.P["muted"])
        def toggled():
            if v.get() and not profile.get(ctx.cfg)[0]:
                setup()
                if not profile.get(ctx.cfg)[0]: v.set(False); return
            ctx.cfg["ai_sep_on"] = v.get(); ctx.save_cfg(); refresh()
        def setup():
            note = _setup(page, "")
            if note is not None: info.config(text=profile.describe(ctx.cfg)); (ctx.toast(note, "info") if note else None)
        def refresh():
            info.config(text=profile.describe(ctx.cfg) if v.get() or profile.get(ctx.cfg)[0] else "not set")
        Switch(ctx, f, v, toggled).pack(side="left", padx=(0, 10)); Btn(ctx, f, "Choose…", lambda: (setup(), refresh()), "secondary", pady=5).pack(side="left")
        info.pack(side="left", padx=(10, 0)); page.setters["ai_sep_on"] = lambda: (v.set(bool(ctx.cfg.get("ai_sep_on", False))), refresh())
        return f
    return D("AI & Import", "Use a different AI for the AI button", "On: the AI button uses its own service and model (for example a free local model), while picture import keeps the one on the Import & AI page.", make)
