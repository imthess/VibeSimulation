"""Shared drawing helpers for component symbols."""
import math

from ..core.render import MUTED, OUTLINE, FILL


def bez(p0, p1, p2, n=12):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(n + 1)]]


def gate_outline(kind, x0, x1, y, h):
    """Outline of a gate body spanning x0..x1 and centred on y. kind: AND, OR, NOT or BUF."""
    top, bot, w = y - h / 2, y + h / 2, x1 - x0
    if kind in ("NOT", "BUF"):
        return [(x0, top), (x1, y), (x0, bot)]
    if kind == "AND":
        rx = min(h / 2, w / 2)
        cx = x1 - rx
        pts = [(x0, top), (cx, top)]
        pts += [(cx + rx * math.cos(-math.pi / 2 + math.pi * k / 16), y + (h / 2) * math.sin(-math.pi / 2 + math.pi * k / 16)) for k in range(1, 16)]
        return pts + [(cx, bot), (x0, bot)]
    return (bez((x0, top), (x0 + w * 0.6, top), (x1, y)) + bez((x1, y), (x0 + w * 0.6, bot), (x0, bot))[1:]
            + bez((x0, bot), (x0 + w * 0.3, y), (x0, top))[1:])


def draw_port_labels(r, ax, ay, ports, size=8):
    """Small captions inside the body, next to each pin that has a label."""
    for p in ports:
        if not p.label:
            continue
        x, y = ax + p.dx, ay + p.dy
        if p.side == "left": r.text(x + 3, y, p.label, size, MUTED, anchor="w")
        elif p.side == "right": r.text(x - 3, y, p.label, size, MUTED, anchor="e")
        elif p.side == "top": r.text(x, y + 3, p.label, size, MUTED, anchor="n")
        else: r.text(x, y - 3, p.label, size, MUTED, anchor="s")


def draw_box(r, ax, ay, body, ctx, symbol="", ports=(), sym_size=14):
    x0, y0, x1, y1 = body
    r.rect(ax + x0, ay + y0, ax + x1, ay + y1, FILL, OUTLINE, 2, ctx.body_tags)
    if symbol:
        r.text(ax + (x0 + x1) / 2 + 4, ay + (y0 + y1) / 2, symbol, sym_size, OUTLINE, True, "c", ctx.body_tags)
    draw_port_labels(r, ax, ay, ports)


def draw_pins(r, ax, ay, comp, ctx):
    """Small dots on every connection point, like Logisim."""
    for p in comp.active_ports():
        r.circle(ax + p.dx, ay + p.dy, 2, MUTED, MUTED, 1, ctx.body_tags)


def draw_gate(r, ax, ay, comp, ctx, kind, w, h, bubble=False, xor=False, label=""):
    """Classic gate symbol. (ax, ay) is the output pin; the body ends at the pin (or at the bubble)."""
    end = -10 if bubble else 0
    x0 = -w + (10 if xor else 0)
    pts = gate_outline(kind, ax + x0, ax + end, ay, h)
    r.polygon(pts, FILL, OUTLINE, 2, ctx.body_tags)
    if xor:
        arc = bez((ax - w, ay - h / 2), (ax - w + 12, ay), (ax - w, ay + h / 2))
        r.line(arc, 2, OUTLINE, ctx.body_tags)
    if bubble:
        r.circle(ax - 5, ay, 5, FILL, OUTLINE, 2, ctx.body_tags)
    if label:
        r.text(ax - w / 2 - 2, ay, label, 11, OUTLINE, True, "c", ctx.body_tags)
    for p in comp.active_ports():
        if p.direction == "in":
            r.line([(ax + p.dx, ay + p.dy), (ax + x0 + (6 if kind in ("OR",) or xor else 0), ay + p.dy)], 2, OUTLINE, ctx.body_tags)
