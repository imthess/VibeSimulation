"""Logisim box 2: the circuit as editable JSON (updates the other boxes live)."""
import re

from ..views.code_view import CodeView


class JsonView(CodeView):
    number, title, hint = None, "Circuit JSON", "edits update live"
    NAME = "JSON"

    # ---- finding the lines a message is about
    def error_lines(self, errors):
        """Work out which lines of the JSON text the error messages are about (1-based)."""
        lines = self.txt.get("1.0", "end").split("\n"); found = set()
        items = [i + 1 for i, l in enumerate(lines) if l.lstrip().startswith("{") and '"type"' in l]
        def with_id(x):
            pat = re.compile(r'"id"\s*:\s*"' + re.escape(x) + r'"')
            return [i + 1 for i, l in enumerate(lines) if pat.search(l)]
        for m in errors:
            m = str(m); hit = re.search(r"\(line (\d+)", m)
            if hit: found.add(int(hit.group(1))); continue
            hit = re.match(r"Item #(\d+)", m)
            if hit and int(hit.group(1)) <= len(items): found.add(items[int(hit.group(1)) - 1]); continue
            hit = re.match(r"([^\s:]+): ", m)
            if hit:
                ids = with_id(hit.group(1))
                if not ids:
                    hit2 = re.fullmatch(r"g(\d+)", hit.group(1))
                    if hit2 and int(hit2.group(1)) <= len(items): ids = [items[int(hit2.group(1)) - 1]]
                found.update(ids)
            for name in re.findall(r"'([^']+)'", m):
                if m.startswith("Two components"): found.update(with_id(name))
                elif m.startswith(("Output", "Signal")) or "nothing drives" in m or "has no pin" in m:
                    found.update(i + 1 for i, l in enumerate(lines) if f'"{name}"' in l)
            if m.startswith(("No inputs", "No outputs")):
                key = '"inputs"' if "inputs" in m else '"outputs"'
                found.update(i + 1 for i, l in enumerate(lines) if key in l)
            if m.startswith("Circuit contains a loop"): found.update(items)
        return found

    def mark_errors(self, errors):
        self.mark_lines(self.error_lines(errors) if errors else set())

    # ---- typing -> document
    def flush_text(self, text):
        if text != self.doc.text.rstrip("\n"):
            self.doc.set_text(text)

    layout_prefix = "The netlist is valid but the wires cannot be drawn cleanly: "

    def ok_kind(self, d): return "ok"

    def ok_text(self, d):
        c = d.circuit
        return f"✔ Valid circuit: {len(c.inputs)} inputs, {len(c.components)} components, {len(c.outputs)} outputs"

    # ---- document -> screen
    def on_doc(self, kind):
        if kind != "changed":
            return
        if self.get_text() != self.doc.text.rstrip("\n"): self.show_text(self.doc.text)
        d = self.doc
        self.mark_errors([] if (d.valid or d.layout_error) else d.errors)
        if d.valid:
            self.status.set(self.ok_text(d), self.ok_kind(d))
        elif d.layout_error:
            self.status.set("✘ " + self.layout_prefix + d.layout_error, "bad")
        else:
            self.status.set("✘ " + "\n✘ ".join(d.errors), "bad")
        self.b_undo.set_enabled(d.can_undo()); self.b_redo.set_enabled(d.can_redo())
