"""The Markdown report drawn into a PDF (A4, no extra library)."""
from vibesimulation.common.pdf_writer import Page, assemble, text_width

W, H, M = 595, 842, 40


def _wrap(s, size, width, bold=False):
    out, cur = [], ""
    for word in s.split(" "):
        while text_width(word, size, bold) > width and len(word) > 1:          # a very long word (a URL, JSON) is cut where it no longer fits
            k = max(1, int(len(word) * width / text_width(word, size, bold)) - 1)
            if cur: out.append(cur); cur = ""
            out.append(word[:k]); word = word[k:]
        t = (cur + " " + word).strip() if cur else word
        if text_width(t, size, bold) <= width: cur = t
        else: out.append(cur); cur = word
    return out + [cur] if cur or not out else out


def build(markdown):
    pages = []; pg = None; y = 0
    def new():
        nonlocal pg, y
        pg = Page(W, H); pages.append(pg); y = H - M; pg.text(W - M, 22, f"page {len(pages)}", 8, "#6a7285", align="r")
    new()
    for raw in markdown.split("\n"):
        size, bold, col, line = 8, False, "#222222", raw.replace("```json", "").replace("```", "")
        if raw.startswith("# "): size, bold, line = 16, True, raw[2:]
        elif raw.startswith("## "): size, bold, line, col = 12, True, raw[3:], "#4f46e5"; y -= 6
        line = line.replace("**", "")
        if raw.strip() == "```" or raw.strip() == "```json": continue
        for part in _wrap(line, size, W - 2 * M, bold) or [""]:
            if y < M + 14: new()
            pg.text(M, y, part, size, col, bold); y -= size * 1.35
    return assemble(pages)
