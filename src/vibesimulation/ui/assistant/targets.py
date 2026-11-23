"""What the assistant edits, per workspace (Strategy pattern).

A target says which text the AI sees, which rules it must follow, how to read the answer, how to check it WITHOUT changing the document,
and how to apply it (through the Document, so Undo works). Nothing here uses Tk widgets except to read the editor box the user is looking at."""
import difflib
import json
import re

import vibesimulation.workspaces.logisim.core.layoutstate as LS
from vibesimulation.workspaces.logisim.core.serializer import dumps, parse
from vibesimulation.workspaces.ai_import.imports import classify
from vibesimulation.workspaces.logisim.layout.engine import LayoutEngine
from vibesimulation.workspaces.ai_import.core import extract_json
from vibesimulation.workspaces.ai_import.core.prompt import ANALOG_HELP, code_rules, digital_help
from vibesimulation.workspaces.multisim.core.netlist import dumps as adumps, parse as aparse
from vibesimulation.workspaces.multisim.core.solver import SolveError
KEYS = ("logisim", "multisim", "vlsi", "systemverilog")


class Target:
    key = noun = ""
    code = False                 # True: the answer is source code; False: one JSON object
    lang = "json"
    example = ""

    def __init__(self, shell):
        self.sh = shell

    # ---- what is being edited
    @property
    def page(self): return self.sh.pages[self.key]

    @property
    def doc(self): return self.sh.cur_doc_of(self.key) if hasattr(self.sh, "cur_doc_of") else {"multisim": self.sh.adoc, "vlsi": self.sh.vdoc, "systemverilog": self.sh.sdoc}.get(self.key, self.sh.doc)

    @property
    def label(self): return self.noun

    def editor(self): return self.page.editor()

    def current(self):
        """The text the user is looking at (typed text that has not been compiled yet is included)."""
        try: self.editor().flush()
        except Exception: pass
        return self.doc.text

    def selection(self):
        """Hint about what the user marked in the editor box or in the drawing (empty when nothing)."""
        try:
            t = self.editor().txt; r = t.tag_ranges("sel")
            if r:
                a, b = int(str(r[0]).split(".")[0]), int(str(r[-1]).split(".")[0])
                if t.get(r[0], r[-1]).strip(): return f"The user has selected lines {a}-{b} of the text: make the change there, unless the request clearly names something else."
        except Exception: pass
        return ""

    def problems(self): return []

    # ---- prompts
    def rules(self): raise NotImplementedError

    def system(self, mode="edit"):
        if mode == "ask":
            return (f"You are a friendly, precise teaching assistant inside VibeSimulation, a circuit simulator. The user shows you their {self.noun.lower()} and asks a question. "
                    "Answer in plain language, briefly (at most about 12 lines), and point to parts by their names. Do not return the whole circuit or file unless asked.")
        return (f"You are the editing assistant inside VibeSimulation, a circuit simulator. The user describes a change and shows their {self.noun.lower()}. "
                f"Apply the change and return the COMPLETE updated {'file' if self.code else 'circuit'} {self.fmt()}, and nothing else: no explanation. "
                "Change only what the request asks for: keep every other name, id and connection exactly as it is. If the request is impossible or unclear, return it unchanged.\n\n" + self.rules())

    def fmt(self): return "as ONE JSON object" if not self.code else f"in ONE ```{self.lang} code block"

    def user(self, request, current, mode="edit"):
        parts = [f"REQUEST:\n{request.strip()}", f"CURRENT {self.noun.upper()}:\n```{self.lang}\n{current.rstrip()}\n```"]
        sel = self.selection(); pr = self.problems()
        if sel: parts.append(sel)
        if pr: parts.append("Problems the program reports about it right now:\n" + "\n".join("- " + p for p in pr[:8]))
        return "\n\n".join(parts)

    def user_fix(self, request, current, bad, errors):
        return (f"REQUEST:\n{request.strip()}\n\nCURRENT {self.noun.upper()}:\n```{self.lang}\n{current.rstrip()}\n```\n\n"
                f"Your previous answer was rejected:\n```{self.lang}\n{bad.rstrip()}\n```\nProblems found:\n" + "\n".join("- " + e for e in errors[:10]) +
                f"\n\nReturn the corrected, COMPLETE {'file' if self.code else 'circuit'} {self.fmt()}, and nothing else.")

    # ---- the answer
    def extract(self, reply):
        """The new document text from the model's answer; raises ValueError with a plain message."""
        raise NotImplementedError

    def check(self, text):
        """Problems that would stop the text from being used ([] = fine). Never changes the document."""
        raise NotImplementedError

    def apply(self, text):
        raise NotImplementedError

    def summary(self, old, new): return "no change" if old.strip() == new.strip() else "updated"


# ------------------------------------------------------------------------------------------- JSON circuits
def _items(text):
    try: raw = json.loads(text)
    except ValueError: return {}, set(), set()
    if not isinstance(raw, dict): return {}, set(), set()
    its = raw.get("gates", raw.get("components", []))
    d = {str(i.get("id")): json.dumps(i, sort_keys=True) for i in its if isinstance(i, dict) and i.get("id") is not None} if isinstance(its, list) else {}
    names = lambda k: {(x["name"] if isinstance(x, dict) else str(x)) for x in raw.get(k, [])} if isinstance(raw.get(k), list) else set()
    return d, names("inputs"), names("outputs")


def _list(names, n=4):
    names = sorted(names); return ", ".join(names[:n]) + (f" +{len(names) - n} more" if len(names) > n else "")


def json_summary(old, new):
    a, ai, ao = _items(old); b, bi, bo = _items(new); out = []
    add, rem = set(b) - set(a), set(a) - set(b); chg = {k for k in set(a) & set(b) if a[k] != b[k]}
    if add: out.append("added " + _list(add))
    if rem: out.append("removed " + _list(rem))
    if chg: out.append("changed " + _list(chg))
    if ai != bi: out.append("inputs " + ", ".join(([f"+{x}" for x in sorted(bi - ai)] + [f"-{x}" for x in sorted(ai - bi)])))
    if ao != bo: out.append("outputs " + ", ".join(([f"+{x}" for x in sorted(bo - ao)] + [f"-{x}" for x in sorted(ao - bo)])))
    return " · ".join(out) if out else "no change"


class LogisimTarget(Target):
    key, noun, lang = "logisim", "Logisim circuit", "json"
    example = "add a NOT gate between A and the output"

    def rules(self):
        return (digital_help() + "\n\nEditing rules: keep the ids of existing parts; give new parts new unique ids (g7, g8, ...). Do not write positions or wires. "
                "Return only the circuit object (it may start with {\"kind\":\"digital\", ...}); never an array and never several circuits.")

    def problems(self): return [] if self.doc.valid else [str(e) for e in self.doc.errors[:8]]

    def selection(self):
        s = super().selection()
        try:
            ids = sorted(self.page.views["circuit"].sels)
            if ids: s = (s + " " if s else "") + "The user has selected these parts in the drawing: " + ", ".join(ids) + ". The request most likely refers to them."
        except Exception: pass
        return s

    def extract(self, reply):
        raw = extract_json(reply)
        if classify(raw) == "analog": raise ValueError("The answer is an analog circuit. Use the Multisim target for resistors, capacitors, transistors, op-amps ...")
        if isinstance(raw.get("circuits"), dict): raise ValueError("The answer holds several circuits; one circuit was expected.")
        c, errs = parse(raw)
        if c is None or errs: raise ValueError("; ".join(str(e) for e in errs) or "The circuit could not be read.")
        return dumps(c)

    def check(self, text):
        c, errs = parse(text)
        if c is None or errs: return [str(e) for e in errs] or ["The circuit could not be read."]
        LS.apply(c, self.doc.state)
        errs = c.validate(loose=True)
        if errs: return [str(e) for e in errs]
        try: LayoutEngine().build(c)
        except ValueError as e: return ["The circuit is valid but cannot be drawn cleanly: " + str(e)]
        return []

    def apply(self, text): self.doc.set_text(text)

    def summary(self, old, new): return json_summary(old, new)


class MultisimTarget(Target):
    key, noun, lang = "multisim", "Multisim circuit", "json"
    example = "change R2 to 4.7k and add a 100n capacitor across it"

    def rules(self):
        return (ANALOG_HELP + "\n\nEditing rules: keep the ids of existing parts; give new parts new ids (R5, C2, ...). Do not write positions or wires. "
                "Return only the circuit object, starting with {\"kind\":\"analog\", ...}. Every circuit needs a ground node named \"0\".")

    def problems(self):
        d = self.doc; out = [str(e) for e in d.errors[:8]]
        if d.layout_error: out.append(str(d.layout_error))
        return out

    def extract(self, reply):
        raw = extract_json(reply)
        if classify(raw) == "digital": raise ValueError("The answer is a logic circuit (gates). Use the Logisim target for gates, adders, flip-flops ...")
        nl, errs = aparse(raw)
        if nl is None or errs: raise ValueError("; ".join(str(e) for e in errs) or "The circuit could not be read.")
        return adumps(nl)

    def check(self, text):
        nl, errs = aparse(text)
        if nl is None or errs: return [str(e) for e in errs] or ["The circuit could not be read."]
        errs = nl.validate()
        if errs: return [str(e) for e in errs]
        try: nl.solve()
        except SolveError as e: return [str(e)]
        return []

    def apply(self, text): self.doc.set_text(text)

    def summary(self, old, new): return json_summary(old, new)


# ------------------------------------------------------------------------------------------- source code
FENCE = re.compile(r"```[A-Za-z0-9_+\-]*[ \t]*\r?\n(.*?)```", re.S)


def extract_code(reply):
    """The source code in a model answer: the biggest ``` block, or the whole answer when it has no block."""
    blocks = FENCE.findall(reply or "")
    if not blocks:
        t = (reply or "").strip()
        if t.startswith("```"): t = re.sub(r"^```[A-Za-z0-9_+\-]*\s*", "", t); t = re.sub(r"```\s*$", "", t)
        blocks = [t]
    code = max(blocks, key=len).strip("\n")
    if not code.strip(): raise ValueError("The answer had no code in it.")
    return code + "\n"


def code_summary(old, new):
    a, b = old.strip().splitlines(), new.strip().splitlines()
    if a == b: return "no change"
    add = rem = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"): rem += i2 - i1
        if tag in ("replace", "insert"): add += j2 - j1
    return f"{add} line{'s' if add != 1 else ''} added, {rem} removed"


class VerilogTarget(Target):
    key, noun, lang, code = "vlsi", "Verilog", "verilog", True
    std = "Verilog (IEEE 1364-2005)"
    example = "make this an 8-bit adder with a carry in"

    @property
    def tb(self):
        try: return self.editor().mode == "tb"
        except Exception: return False

    @property
    def label(self): return self.noun + (" testbench" if self.tb else "")

    def current(self):
        try: self.editor().flush()
        except Exception: pass
        try: return self.editor().get_text()                           # exactly what the user sees, also text that does not compile yet
        except Exception: return self.doc.tb_text if self.tb else self.doc.verilog()

    def problems(self):
        if self.tb: return []
        return [f"{'error' if s == 'error' else 'warning'} line {ln}: {m}" for s, ln, m in self.doc.problems[:8]]

    def rules(self):
        if self.tb:
            return (f"You write testbenches for {self.std}. The testbench is run by VibeSimulation's own simulator: use `module tb;` (no ports), reg/wire declarations, instantiate the design, "
                    "`initial` and `always` blocks, #delays, $display, $monitor, $finish. Keep it simple and self-checking where possible.")
        return code_rules(self.key)

    def extract(self, reply): return extract_code(reply)

    def check(self, text):
        if self.tb: return [] if "module" in text else ["A testbench needs a `module`."]
        d = self.doc; circuits = {n: e["text"] for n, e in d.circuits.items()}; circuits[d.cur] = d.text
        res = d.compile(text, circuits, d.cur)
        return [f"line {ln}: {m}" for ln, m in res.errors]

    def apply(self, text):
        if self.tb: self.doc.set_testbench(text); return
        errs = self.doc.set_verilog(text)
        if errs: raise ValueError("; ".join(f"line {ln}: {m}" for ln, m in errs[:3]))

    def summary(self, old, new): return code_summary(old, new)


class SystemVerilogTarget(VerilogTarget):
    key, noun, lang = "systemverilog", "SystemVerilog", "systemverilog"
    std = "SystemVerilog (IEEE 1800)"
    example = "turn this into a parameterised counter with enable"


TARGETS = {"logisim": LogisimTarget, "multisim": MultisimTarget, "vlsi": VerilogTarget, "systemverilog": SystemVerilogTarget}
NAMES = {"logisim": "Logisim circuit", "multisim": "Multisim circuit", "vlsi": "Verilog", "systemverilog": "SystemVerilog"}


def target_for(shell, key):
    return TARGETS[key if key in TARGETS else "logisim"](shell)
