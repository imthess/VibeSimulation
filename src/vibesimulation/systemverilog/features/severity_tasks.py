"""$error, $warning, $info, $fatal: printed with $display (the fatal one also ends the run)."""
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..lexer import Tok
from ..scan import group_end, semi_end

LEVEL = {"$error": "ERROR", "$warning": "WARNING", "$info": "INFO", "$fatal": "FATAL"}


def split_args(toks, a, b):
    out, cur, k = [], [], a
    while k < b:
        x = toks[k]
        if x.kind == "op" and x.text in ("(", "[", "{"): e = group_end(toks, k); cur += toks[k:e]; k = e; continue
        if x.kind == "op" and x.text == ",": out.append(cur); cur = []
        else: cur.append(x)
        k += 1
    if cur or out: out.append(cur)
    return out


@feature
class SeverityTasks(Feature):
    name = "severity_tasks"
    summary = "$error / $warning / $info / $fatal"
    order = 96
    triggers = tuple(LEVEL)

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor(); i = 0
        while i < len(toks):
            t = toks[i]
            if not (t.kind == "sys" and t.text in LEVEL): i += 1; continue
            tag = LEVEL[t.text]; call_end = i + 1; args = []
            if toks[i + 1].text == "(": call_end = group_end(toks, i + 1); args = split_args(toks, i + 2, call_end - 1)
            if t.text == "$fatal" and args and len(args[0]) == 1 and args[0][0].kind == "num": args = args[1:]
            if args and len(args[0]) == 1 and args[0][0].kind == "str": first = Tok("str", '"' + tag + ": " + args[0][0].text[1:], t.line); rest = args[1:]
            else: first = Tok("str", f'"{tag}"', t.line); rest = args
            call = [Tok("sys", "$display", t.line), Tok("op", "(", t.line), first]
            for a in rest: call += [Tok("op", ",", t.line)] + a
            call.append(Tok("op", ")", t.line))
            end = semi_end(toks, call_end - 1) if toks[call_end].text == ";" else call_end
            if t.text == "$fatal": ed.replace(i, end, [Tok("id", "begin", t.line)] + call + [Tok("op", ";", t.line), Tok("sys", "$finish", t.line), Tok("op", ";", t.line), Tok("id", "end", t.line)])
            else: ed.replace(i, call_end, call)
            i = end
        ctx.commit(ed)
