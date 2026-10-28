"""The testbench side of a VLSI project: keeping the testbench text apart from the design, and finding modules in it."""
from ..verilog.lexer import VError
from ..verilog.parser import parse_modules
from ..verilog.tb.split import has_processes


def module_slices(text, prepare=None):
    """[(name, first line, text)] of the modules in `text` (anything before the first module is dropped).
    `prepare` turns the text into Verilog first (the SystemVerilog section lowers it); line numbers do not change."""
    mods, _ = parse_modules(prepare(text) if prepare else text)
    lines = text.split("\n"); starts = sorted(m.line for m in mods) + [len(lines) + 1]
    out = []
    for m in mods:
        i = starts.index(m.line)
        out.append((m.name, m.line, "\n".join(lines[m.line - 1:starts[i + 1] - 1]).rstrip() + "\n"))
    return out


def merge(old_text, new_slices, prepare=None):
    """Put the modules of `new_slices` {name: text} into `old_text`, replacing modules with the same name."""
    try: kept = [(n, t) for n, _, t in module_slices(old_text, prepare) if n not in new_slices]
    except VError: kept = [("", old_text)] if old_text.strip() else []
    return "\n".join([t for _, t in kept] + list(new_slices.values()))


def testbench_names(text, prepare=None):
    """Names of the testbench modules in `text` ([] when it has none or cannot be read)."""
    try: mods, _ = parse_modules(prepare(text) if prepare else text)
    except VError: return []
    return [m.name for m in mods if has_processes(m)]
