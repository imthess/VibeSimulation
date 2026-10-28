"""SystemVerilog tokens. Unlike the Verilog lexer this one keeps the text of every token (and the comments), so the token list can be
written back as Verilog with each token still on the line it came from."""
import re

from ..verilog.lexer import VError


class Tok:
    __slots__ = ("kind", "text", "line")

    def __init__(self, kind, text, line): self.kind, self.text, self.line = kind, text, line

    def __repr__(self): return f"{self.kind}:{self.text!r}@{self.line}"


OPS = ["<<<=", ">>>=", "<<=", ">>=", "===", "!==", "==?", "!=?", "<<<", ">>>", "<->", "|->", "|=>", "++", "--", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
       "::", "->", "=>", "**", "&&", "||", "<=", ">=", "==", "!=", "<<", ">>", "~&", "~|", "~^", "^~", "+:", "-:", ".*", "'{", "##",
       "+", "-", "*", "/", "%", "&", "|", "^", "~", "!", "<", ">", "=", "?", ":", ";", ",", ".", "(", ")", "[", "]", "{", "}", "#", "@", "'", "$"]
_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")
_SYS = re.compile(r"\$[A-Za-z_][A-Za-z0-9_$]*")
_BASED = re.compile(r"(?:[0-9][0-9_]*)?[ \t]*'[sS]?[bBoOdDhH][ \t]*[0-9a-fA-FxXzZ_?]+")
_FILL = re.compile(r"'[01xXzZ](?![0-9A-Za-z_])")
_NUM = re.compile(r"[0-9][0-9_]*(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


def lex(text):
    """-> [Tok]; the last one is ('eof')."""
    toks, i, line, n = [], 0, 1, len(text)
    while i < n:
        c = text[i]
        if c == "\n": line += 1; i += 1; continue
        if c in " \t\r\f": i += 1; continue
        if text.startswith("//", i):
            j = text.find("\n", i); j = n if j < 0 else j
            toks.append(Tok("comment", text[i:j].rstrip(), line)); i = j; continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0: raise VError("unterminated /* comment", line)
            toks.append(Tok("comment", text[i:j + 2], line)); line += text.count("\n", i, j); i = j + 2; continue
        if text.startswith("(*", i) and not text.startswith("(*)", i):
            j = text.find("*)", i + 2)
            if j < 0: raise VError("unterminated (* attribute", line)
            line += text.count("\n", i, j); i = j + 2; continue                      # attributes carry no meaning here
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\": j += 1
                j += 1
            toks.append(Tok("str", text[i:j + 1], line)); line += text.count("\n", i, j); i = j + 1; continue
        if c == "`": raise VError("a compiler directive (`" + (text[i + 1:].split() or [""])[0][:20] + ") is not supported here", line)
        if c == "\\":
            j = i + 1
            while j < n and not text[j].isspace(): j += 1
            toks.append(Tok("id", text[i:j], line)); i = j; continue
        if c == "$":
            m = _SYS.match(text, i)
            if m: toks.append(Tok("sys", m.group(), line)); i = m.end(); continue
        if c.isdigit() or c == "'":
            m = _BASED.match(text, i)
            if m: toks.append(Tok("num", re.sub(r"[ \t]+", "", m.group()), line)); i = m.end(); continue
            m = _FILL.match(text, i)
            if m: toks.append(Tok("fill", m.group(), line)); i = m.end(); continue
            if c.isdigit():
                m = _NUM.match(text, i); toks.append(Tok("num", m.group(), line)); i = m.end(); continue
        m = _ID.match(text, i)
        if m: toks.append(Tok("id", m.group(), line)); i = m.end(); continue
        for op in OPS:
            if text.startswith(op, i): toks.append(Tok("op", op, line)); i += len(op); break
        else: raise VError(f"unexpected character {c!r}", line)
    toks.append(Tok("eof", "", line))
    return toks


def emit(tokens):
    """Tokens -> text, each token on its own line. A // comment that other text now follows becomes a /* */ comment."""
    lines, cur, line = [], [], 1
    def close():
        parts = []
        for k, t in enumerate(cur):
            s = t.text
            if t.kind == "comment" and s.startswith("//") and k < len(cur) - 1: s = "/* " + s[2:].strip().replace("*/", "* /") + " */"
            parts.append(s)
        lines.append(" ".join(parts))
    for t in tokens:
        if t.kind == "eof": break
        if t.line > line:
            close(); lines.extend([""] * (t.line - line - 1)); cur = []; line = t.line
        cur.append(t)
        if t.kind == "comment" and "\n" in t.text: line += t.text.count("\n")      # a multi-line comment moves the line counter; the next tokens continue on its last line
    close()
    return "\n".join(lines) + "\n"
