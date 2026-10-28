"""SystemVerilog functions and tasks: `function void` becomes a task, and `return expr;` assigns the function's name.

A `return` is accepted where it is the last thing the function does (at the end of the body, or at the end of every branch of a final
if / else / case). An early `return` in the middle would need the rest of the body to be skipped, which Verilog cannot say."""
from ..analysis import at_statement_start
from ..editor import toks as snippet
from ..feature import Feature, feature
from ..lexer import Tok
from ..scan import block_end, group_end, semi_end, stmt_end


def statements(toks, a, b):
    out = []; i = a
    while i < b:
        if toks[i].kind == "comment": i += 1; continue
        e = stmt_end(toks, i); out.append((i, e)); i = e
    return out


def tail_ranges(toks, s, e):
    """Statement ranges where a `return` may stand: the statement itself, or the tails of its branches."""
    t = toks[s]
    if t.kind == "id" and t.text == "begin":
        k = s + 1
        if toks[k].text == ":": k += 2
        inner = statements(toks, k, e - 1)
        return tail_ranges(toks, *inner[-1]) if inner else []
    if t.kind == "id" and t.text == "if":
        c = group_end(toks, s + 1); thn_end = stmt_end(toks, c); out = tail_ranges(toks, c, thn_end)
        k = thn_end
        while toks[k].kind == "comment": k += 1
        if toks[k].text == "else": out += tail_ranges(toks, k + 1, e)
        return out
    if t.kind == "id" and t.text in ("case", "casez", "casex"):
        out = []; k = group_end(toks, s + 1)
        while k < e - 1:
            if toks[k].kind == "comment": k += 1; continue
            if toks[k].text == "endcase": break
            while not (toks[k].text == ":" and toks[k].kind == "op") and toks[k].text != "default": k = group_end(toks, k) if toks[k].text in ("(", "[", "{") else k + 1
            if toks[k].text == "default": k += 1
            if toks[k].text == ":": k += 1
            se = stmt_end(toks, k); out += tail_ranges(toks, k, se); k = se
        return out
    return [(s, e)]


@feature
class Functions(Feature):
    name = "functions"
    summary = "function void -> task; return expr; -> name = expr;"
    order = 90
    triggers = ("function", "task", "return")

    def apply(self, ctx):
        toks = ctx.tokens; ed = ctx.editor()
        for i, t in enumerate(toks):
            if not (t.kind == "id" and t.text == "function"): continue
            end = block_end(toks, i); h = i + 1; d = 0
            while not (toks[h].text == ";" and d == 0):
                if toks[h].text == "(" : d += 1
                elif toks[h].text == ")": d -= 1
                h += 1
            header = toks[i + 1:h]
            void = any(x.text == "void" for x in header[:3])
            name = None
            for k, x in enumerate(header):
                if x.text == "(": break
                if x.kind == "id" and x.text not in ("void", "automatic", "signed", "unsigned", "logic", "bit", "int", "integer", "byte", "shortint", "longint", "reg"): name = x.text
            if name is None: ctx.fail(t.line, "the function needs a name")
            body_a = h + 1; body_b = end - 1
            tails = []
            stmts = statements(toks, body_a, body_b)
            if stmts: tails = tail_ranges(toks, *stmts[-1])
            for a, b in statements(toks, body_a, body_b) if False else []: pass
            for k in range(body_a, body_b):
                x = toks[k]
                if x.kind == "id" and x.text == "return":
                    stmt_e = semi_end(toks, k)
                    if not any(a <= k and stmt_e <= b for a, b in tails): ctx.fail(x.line, f"SystemVerilog: this 'return' is not the last thing {name} does; end the function with the return or put it at the end of each if / else branch")
                    if void:
                        ed.replace(k, stmt_e, [Tok("op", ";", x.line)]) if stmt_e - k == 2 else ctx.fail(x.line, "a void function cannot return a value")
                    else:
                        if stmt_e - k == 2: ctx.fail(x.line, "return needs a value in a function")
                        ed.replace(k, k + 1, [Tok("id", name, x.line), Tok("op", "=", x.line)])
            if void:
                ed.replace(i, i + 1, [Tok("id", "task", t.line)]); ed.replace(end - 1, end, [Tok("id", "endtask", toks[end - 1].line)])
                v = next(k for k in range(i + 1, h) if toks[k].text == "void"); ed.delete(v, v + 1)
        ctx.commit(ed)
