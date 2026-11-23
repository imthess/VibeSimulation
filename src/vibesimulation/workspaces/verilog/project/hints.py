"""Which line of the Verilog made which part: the `// @id` comments that generated Verilog puts after each statement."""
import re

_HINT = re.compile(r"//\s*@(\S+)")


def lines_from_hints(text):
    """{part id: first line (1-based) that names it}"""
    out = {}
    for i, line in enumerate(text.split("\n"), 1):
        for m in _HINT.finditer(line): out.setdefault(m.group(1), i)
    return out


def parts_on_line(partlines, line):
    """Ids of the parts made by the statement on `line`."""
    return {pid for pid, ln in partlines.items() if ln == line}
