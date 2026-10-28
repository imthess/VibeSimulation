"""File actions of the VLSI page: open and save .v files, plus the downloads it shares with Logisim (.circ, PDF, CSV)."""
import re

from ..actions import FileActions
from ...vlsi.samples import BLANK


class VlsiActions(FileActions):
    """FileActions on the VLSI document. The menu's 'circuit JSON' entries mean Verilog files here."""
    LABELS = {"open": "Open Verilog file (.v)…", "save": "Save Verilog…", "export": "Verilog (.v)"}
    EXT, DIALOG_EXTS, BLANK = ".v", [".v", ".sv", ".txt"], BLANK        # the SystemVerilog actions change these

    def _ready(self, what):
        if not self.doc.valid:
            self.ctx.say(what, "There is no valid circuit yet. Fix the Verilog first."); return False
        return True

    # ---- Verilog files
    def verilog_save(self):
        d = self.doc
        text = d.verilog_project()
        if not text.strip(): self.ctx.say("Export Verilog", "There is no circuit yet."); return
        used = sorted(set(re.findall(r"\bvs_\w+", text)))
        head = "// Written by VibeSimulation.\n"
        if used: head += f"// Library parts used ({', '.join(used)}) are VibeSimulation cells with Logisim's behaviour; other tools need their own models for them.\n"
        p = self._save("Save " + self.LABELS["export"].split(" ")[0], self.EXT, f"{d.cur}{self.EXT}", head + "\n" + text)
        if p: self.ctx.say("Saved", p)

    def verilog_open(self, path=None):
        p = path or self.ctx.choose_file("open", "Open " + self.LABELS["export"].split(" ")[0], self.DIALOG_EXTS)
        if not p: return False
        try:
            with open(p, encoding="utf-8") as f: text = f.read()
        except Exception as e: self.ctx.say("Open Verilog", str(e)); return False
        errs = self.doc.set_verilog(text)
        if errs:
            self.ctx.say("Open Verilog", "\n".join(f"line {ln}: {m}" for ln, m in errs[:8])); return False
        if path: self.ctx.add_recent(path)
        self.doc.set_inputs({}); return True

    # ---- the generic names the menus use
    json_save = verilog_save
    json_open = verilog_open

    def new(self):
        self.doc.new_blank(self.BLANK); self.doc.set_inputs({})
