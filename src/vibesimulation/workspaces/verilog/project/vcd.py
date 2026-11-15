"""Value Change Dump (IEEE 1364 §18) writer: the waveforms of a run in the file format GTKWave, Surfer, ModelSim and Vivado all open."""
import datetime


def _ident(k):
    s = ""
    k += 1
    while k: k, r = divmod(k - 1, 94); s = chr(33 + r) + s
    return s


def _val(v, w):
    if v is None: return "x" if w == 1 else "bx "
    if w == 1: return str(v & 1)
    return "b" + format(v & ((1 << w) - 1), "b") + " "


def to_vcd(res, timescale="1ns", module="top", date=True):
    names = [n for n in res.order if n in res.waves]
    ids = {n: _ident(k) for k, n in enumerate(names)}
    out = []
    if date: out.append(f"$date {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} $end")
    out += ["$version VibeSimulation $end", f"$timescale {timescale} $end", f"$scope module {module} $end"]
    for n in names:
        w = res.widths.get(n, 1); out.append(f"$var {'wire' if res.kinds.get(n) != 'variable' else 'reg'} {w} {ids[n]} {n}{'' if w == 1 else f' [{w - 1}:0]'} $end")
    out += ["$upscope $end", "$enddefinitions $end"]
    ev = {}
    for n in names:
        for t, v in res.waves[n]: ev.setdefault(int(t), []).append((n, v))
    first = True
    for t in sorted(ev):
        out.append(f"#{t}")
        if first and t == 0: out.append("$dumpvars"); first = False; close = True
        else: close = False
        for n, v in ev[t]:
            w = res.widths.get(n, 1); out.append(f"{_val(v, w)}{ids[n]}" if w == 1 else f"{_val(v, w)}{ids[n]}")
        if close: out.append("$end")
    out.append(f"#{int(res.end_time)}")
    return "\n".join(out) + "\n"


def parse_vcd(text):
    """Read back what to_vcd wrote (used by the tests): -> ({name: width}, {name: [(time, int | None)]})."""
    widths, waves, ids, t = {}, {}, {}, 0
    lines = text.split("\n"); i = 0
    while i < len(lines):
        p = lines[i].split(); i += 1
        if not p: continue
        if p[0] == "$var": ids[p[3]] = p[4]; widths[p[4]] = int(p[2]); waves[p[4]] = []
        elif p[0].startswith("#"): t = int(p[0][1:])
        elif p[0] in ("$dumpvars", "$end") or p[0].startswith("$"): continue
        elif p[0][0] == "b": waves[ids[p[1]]].append((t, None if "x" in p[0] else int(p[0][1:], 2)))
        elif p[0][0] in "01xz": waves[ids[p[0][1:]]].append((t, None if p[0][0] in "xz" else int(p[0][0])))
    return widths, waves
