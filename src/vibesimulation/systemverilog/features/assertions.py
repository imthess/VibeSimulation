"""Immediate assertions: `assert (cond) else $error("...");` becomes an if that reports the failure.

Concurrent assertions (assert property, sequences) are not supported."""
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..scan import group_end, semi_end, stmt_end


@feature
class Assertions(Feature):
    name = "assertions"
    summary = "assert (cond) else $error(...)"
    order = 94
    triggers = ("assert", "assume", "cover")

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor(); i = 0
        while i < len(toks):
            t = toks[i]
            if t.kind == "id" and t.text in ("assume", "cover") and toks[i + 1].text == "(": ctx.fail(t.line, f"SystemVerilog: '{t.text}' is not supported")
            if not (t.kind == "id" and t.text == "assert"): i += 1; continue
            if toks[i + 1].text != "(": ctx.fail(t.line, "assert needs its condition in ( )")
            c = group_end(toks, i + 1); cond = toks[i + 2:c - 1]; start = i
            if i >= 2 and toks[i - 1].text == ":" and toks[i - 2].kind == "id": start = i - 2         # a label before the assert
            k = c; ok_stmt = None
            if toks[k].text != ";" and toks[k].text != "else": ok_stmt = (k, stmt_end(toks, k)); k = ok_stmt[1]
            bad = None
            if toks[k].text == "else": bad = (k + 1, stmt_end(toks, k + 1)); k = bad[1]
            elif toks[k].text == ";": k += 1
            text = lambda r: toks[r[0]:r[1]]
            if bad is None: bad_toks = snippet(f'$display("ERROR: assertion failed (line {t.line})");', t.line)
            else: bad_toks = text(bad)
            if ok_stmt is None: new = snippet("if (!(", t.line) + cond + snippet("))", t.line) + [snippet("begin", t.line)[0]] + bad_toks + [snippet("end", t.line)[0]]
            else: new = snippet("if (", t.line) + cond + snippet(")", t.line) + text(ok_stmt) + snippet("else", t.line) + bad_toks
            ed.replace(start, k, new); i = k
        ctx.commit(ed)
