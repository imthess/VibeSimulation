"""Oscilloscope: a transient run seen the way a bench scope shows it.

``capture`` runs the circuit long enough to contain the screen (time/div × divisions), finds the trigger (an edge of channel A or B through a level)
and returns the screen contents: every channel resampled on the same time axis, with its volts/div and offset, plus the readings a scope's
measure menu gives (Vmax, Vmin, Vpp, average, RMS, frequency, period)."""
import math

from . import components as C
from . import measure as M
from . import thermal
from . import transient as TR
from .units import parse_value

DIVS = 10


def sources_period(nl):
    """Longest period among AC sources (a hint for how long to look for a trigger), or None."""
    fs = [p.freq() for p in nl.parts if isinstance(p, C.Waveform) and p.is_ac()]
    return 1.0 / min(fs) if fs else None


def _interp(ts, ys, t):
    lo, hi = 0, len(ts) - 1
    if t <= ts[0]: return ys[0]
    if t >= ts[-1]: return ys[-1]
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ts[mid] <= t: lo = mid
        else: hi = mid
    f = (t - ts[lo]) / (ts[hi] - ts[lo]); return ys[lo] + f * (ys[hi] - ys[lo])


def find_trigger(ts, ys, level, slope, t_from):
    """Time of the first crossing of `level` (rising / falling) at or after t_from, or None."""
    for k in range(1, len(ts)):
        if ts[k] < t_from: continue
        a, b = ys[k - 1], ys[k]
        if (slope == "rising" and a < level <= b) or (slope == "falling" and a > level >= b):
            return ts[k - 1] + (ts[k] - ts[k - 1]) * (level - a) / (b - a) if b != a else ts[k]
    return None


def readings(ts, ys):
    n = len(ys); mean = sum(ys) / n; rms = math.sqrt(sum(y * y for y in ys) / n)
    out = {"vmax": max(ys), "vmin": min(ys), "vpp": max(ys) - min(ys), "avg": mean, "rms": rms, "freq": None, "period": None}
    f = TR.frequency(ts, ys)
    if f: out["freq"], out["period"] = f, 1.0 / f
    return out


def capture(nl, channels, time_per_div, trigger=None, delay=0.0, samples=1000, divs=DIVS, method="trap"):
    """channels: [{"probe": "V(out)", "vdiv": 1.0, "offset": 0.0, "coupling": "dc"|"ac"|"gnd"}]  (up to 4)
    trigger: {"source": 0 (channel index), "level": 0.0, "slope": "rising"|"falling", "mode": "auto"|"normal"}  or None for free run (start at `delay`)
    -> {"t": [0 .. window], "channels": [{..., "y": [...], "read": {...}}], "triggered": bool, "t0": float, "window": float}"""
    if not 1 <= len(channels) <= 4: raise ValueError("Use between 1 and 4 channels.")
    tdiv = parse_value(time_per_div)
    if tdiv <= 0: raise ValueError("Time per division must be greater than 0.")
    delay = max(0.0, parse_value(delay))
    window = tdiv * divs; samples = int(samples)
    spec = {"kind": "dc", "probes": [c["probe"] for c in channels]}
    M.check_spec(nl, spec)
    per = sources_period(nl) if trigger else None
    search = max(window, 1.5 * per) if per else window
    total = delay + search + window; dt = window / samples
    steps = int(math.ceil(total / dt))
    if steps > 60000: raise ValueError("That is too long a look for such a fine time base: raise the time/div or lower the delay (or reduce the trigger search).")
    res = TR.run(nl, total, max(2, steps), method)
    ts = res["t"]; raw = []
    for c in channels:
        p = M.parse_probe(c["probe"])
        if p[0] == "V": a, b = res["V"].get(M._net(p[1])) or [0.0] * len(ts), res["V"].get(M._net(p[2])) or [0.0] * len(ts); raw.append([x - y for x, y in zip(a, b)])
        else: raw.append(res["I"][p[1]])
    t0, triggered = delay, False
    if trigger:
        src = int(trigger.get("source", 0))
        if not 0 <= src < len(channels): raise ValueError("The trigger source must be one of the channels.")
        hit = find_trigger(ts, raw[src], float(trigger.get("level", 0.0)), trigger.get("slope", "rising"), delay)
        if hit is not None and hit + window <= ts[-1] + 1e-15: t0, triggered = hit, True
        elif trigger.get("mode", "auto") == "normal": t0 = None
    out = {"t": [window * k / (samples - 1) for k in range(samples)], "channels": [], "triggered": triggered, "t0": t0, "window": window, "divs": divs, "tdiv": tdiv}
    for c, ys in zip(channels, raw):
        cp = c.get("coupling", "dc")
        item = {"probe": c["probe"], "vdiv": float(c.get("vdiv", 1.0)), "offset": float(c.get("offset", 0.0)), "coupling": cp}
        if t0 is None: item["y"] = None; item["read"] = None
        else:
            y = [_interp(ts, ys, t0 + window * k / (samples - 1)) for k in range(samples)]
            if cp == "ac": m = sum(y) / len(y); y = [v - m for v in y]
            elif cp == "gnd": y = [0.0] * len(y)
            item["y"] = y; item["read"] = readings(out["t"], y)
        out["channels"].append(item)
    thermal.use(nl)
    return out
