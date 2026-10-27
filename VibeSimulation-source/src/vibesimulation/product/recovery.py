"""Autosave and crash recovery.

Every few seconds the three sections are written to one small file (only when something changed since the program started). A normal
exit deletes the file. If it is still there at the next start, the program did not exit normally and offers to bring the work back.
"""
import hashlib
import json
import os
import time
from pathlib import Path

PATH = Path.home() / ".vibesimulation-recovery.json"


def collect(sh):
    """What to save: the text of each section."""
    d = sh.doc
    data = {"time": time.time(), "version": 1,
            "logisim": d.project_text() if (d.text.strip() or len(d.circuits) > 1) else "",
            "multisim": sh.adoc.text,
            "vlsi": {"verilog": sh.vdoc.verilog_project() if sh.vdoc.circuits else "", "tb": sh.vdoc.tb_text}}
    return data


def signature(data):
    d = {k: v for k, v in data.items() if k != "time"}
    return hashlib.sha1(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest()


class Recovery:
    """One per window. start(sh) remembers what the sections look like at the start; save(sh) writes a file when they differ from it."""
    def __init__(self, path=PATH):
        self.path, self.base, self.last = Path(path), None, None

    def start(self, sh): self.base = signature(collect(sh))

    def pending(self):
        """The saved data of an earlier run that did not exit normally, or None."""
        try: data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError): return None
        if not isinstance(data, dict) or not any((data.get("logisim"), data.get("multisim"), (data.get("vlsi") or {}).get("verilog"))): return None
        return data

    def save(self, sh):
        """Write the file if the work changed. Returns True when something was written."""
        data = collect(sh); sig = signature(data)
        if sig == self.base or sig == self.last: return False
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data), encoding="utf-8"); os.replace(tmp, self.path)
        except OSError: return False
        self.last = sig; return True

    def clear(self):
        try: self.path.unlink()
        except OSError: pass

    @staticmethod
    def describe(data):
        when = time.strftime("%d %b %Y, %H:%M", time.localtime(data.get("time", 0)))
        parts = [n for n, k in (("Logisim", "logisim"), ("Multisim", "multisim")) if data.get(k)] + (["VLSI"] if (data.get("vlsi") or {}).get("verilog") else [])
        return when, parts

    @staticmethod
    def restore(sh, data):
        """Put the saved text back into the sections. Returns the list of sections restored."""
        done = []
        if data.get("logisim"):
            sh.doc.load_project(data["logisim"]) if '"circuits"' in data["logisim"][:300] else sh.doc.load_text(data["logisim"]); sh.doc.set_inputs({}); done.append("logisim")
        if data.get("multisim"): sh.adoc.load_text(data["multisim"]); done.append("multisim")
        v = data.get("vlsi") or {}
        if v.get("verilog"):
            sh.vdoc.new_blank(v["verilog"]); sh.vdoc.set_inputs({}); done.append("vlsi")
            if v.get("tb"): sh.vdoc.set_testbench(v["tb"])
        return done
