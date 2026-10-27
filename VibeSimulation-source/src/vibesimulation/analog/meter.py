"""Multimeter: DC voltage, DC current, AC voltage / current (RMS), resistance.

- voltage  between two nets (the second defaults to ground),
- current  through a part (the meter is in series: the reading is that part's current, a → b),
- AC       true RMS of the AC part at the frequency of the AC sources (peak / √2), taken from the small-signal solution,
- ohms     between two nets with every independent source switched off, measured with a small test current like a real meter does.
A circuit with no path between the nets reads "OL" (over limit)."""
import math

from . import ac as AC
from . import components as C
from .solver import SolveError, is_ground
from .units import fmt_si

MODES = {"vdc": ("DC voltage", "V"), "idc": ("DC current", "A"), "vac": ("AC voltage (RMS)", "V"), "iac": ("AC current (RMS)", "A"), "ohm": ("Resistance", "Ω")}
OL = 1e9                 # beyond this many ohms the meter says OL
TEST_CURRENT = 1e-5      # amperes pushed through the circuit by the ohmmeter


def _net(n): return "0" if is_ground(n) else str(n).strip()


def ac_frequency(nl):
    """Frequency of the strongest AC source (None if there is none)."""
    best = max((p for p in nl.parts if isinstance(p, C.Waveform) and p.is_ac()), key=lambda p: abs(p.ac_amp()), default=None)
    return best.freq() if best else None


def _check_net(nl, n):
    if _net(n) not in set(nl.nets()) | {"0"}: raise ValueError(f"The circuit has no net '{n}'.")


def read(nl, mode, a=None, b="0", part=None, f=None):
    """-> {"mode", "value" (float, inf for OL), "unit", "text"}"""
    if mode not in MODES: raise ValueError("Mode must be one of " + ", ".join(MODES))
    errs = nl.validate()
    if errs: raise ValueError(f"The circuit is not valid: {errs[0]}")
    unit = MODES[mode][1]
    if mode in ("idc", "iac"):
        p = nl.part(part) if part else None
        if p is None: raise ValueError(f"Choose the part the current flows through{'' if not part else f' (there is no part {part!r})'}.")
    else:
        if not a: raise ValueError("Choose the net to measure.")
        _check_net(nl, a); _check_net(nl, b or "0")
    try:
        if mode == "vdc":
            volts, _ = nl.solve(); v = volts[_net(a)] - volts[_net(b or "0")]
        elif mode == "idc":
            _, res = nl.solve(); v = res[part][1]
        elif mode in ("vac", "iac"):
            f = f or ac_frequency(nl)
            if not f: raise ValueError("No source has an AC part, so there is nothing for an AC reading (give a source an 'ac' amplitude).")
            prep = AC.prepare(nl); pt = AC.point(prep, f)
            z = (pt["V"][_net(a)] - pt["V"][_net(b or "0")]) if mode == "vac" else pt["parts"][part]["i"]
            v = abs(z) / math.sqrt(2)
        else:
            v = _ohms(nl, _net(a), _net(b or "0"))
    except SolveError as e: raise ValueError(f"The circuit cannot be solved: {e}")
    text = "OL" if abs(v) >= OL else fmt_si(v, unit, int(4))
    return {"mode": mode, "value": v, "unit": unit, "text": text}


def _ohms(nl, a, b):
    if a == b: return 0.0
    dead = nl.copy()
    for p in dead.parts:
        if isinstance(p, (C.VoltageSource, C.CurrentSource)): p.value = "0"; p.extra["ac"] = "0"
    dead.parts.append(C.CurrentSource("Itest_", [b, a], repr(TEST_CURRENT)))
    try: volts, _ = dead.solve()
    except SolveError: return math.inf
    r = (volts[a] - volts[b]) / TEST_CURRENT
    return math.inf if abs(r) >= OL else r
