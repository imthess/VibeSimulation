"""Wires autosave, crash recovery and the background update check into the main window (called once from MainWindow)."""
from ...product.recovery import Recovery
from .about import check_for_updates

INTERVAL = 20000                    # ms between autosaves


class ProductHooks:
    def __init__(self, shell):
        self.sh, self.ctx = shell, shell.ctx; self.rec = Recovery(); self.job = None
        self.pending = self.rec.pending()                          # taken BEFORE this run starts writing its own file
        self.rec.start(shell)

    def start(self):
        root = self.sh.root
        if self.pending: root.after(900, self.offer)
        self.job = root.after(INTERVAL, self.tick)
        if self.ctx.cfg.get("check_updates", False): root.after(4000, lambda: check_for_updates(self.ctx, self.sh, self.quiet, False))

    def quiet(self, text, kind="info", url=""):
        if kind == "ok" and url: self.ctx.toast(text + " See Help > About.", "info")

    def offer(self):
        data = self.pending; self.pending = None
        when, parts = Recovery.describe(data)
        if self.ctx.ask("Restore unsaved work?", f"VibeSimulation did not close normally last time. Work saved automatically on {when} is available ({', '.join(parts)}).\\n\\nRestore it? (Yes puts it back into those workspaces; No discards it.)".replace("\\n", "\n")):
            done = Recovery.restore(self.sh, data); self.rec.start(self.sh)
            self.rec.last = None
            if done: self.sh.show(done[0]); self.ctx.toast("Recovered the autosaved work.")
        else: self.rec.clear()

    def tick(self):
        try:
            if self.ctx.cfg.get("autosave", True): [self.sh.pages[k].views["verilog"].flush() for k in ("vlsi", "systemverilog")]; self.rec.save(self.sh)
        except Exception: pass
        self.job = self.sh.root.after(INTERVAL, self.tick)

    def finish(self):
        """Normal exit: the autosave is not needed any more."""
        if self.job:
            try: self.sh.root.after_cancel(self.job)
            except Exception: pass
        if self.pending is None: self.rec.clear()
