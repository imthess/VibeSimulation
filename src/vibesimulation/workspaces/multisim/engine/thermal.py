"""Temperature. Parts are written for 27 °C (SPICE's TNOM). At another temperature:
- the thermal voltage kT/q changes (every diode / transistor equation reads it),
- saturation currents move with the usual SPICE law  IS(T) = IS (T/Tn)^(XTI/N) exp((T/Tn - 1) EG / (N Vt)),
- resistors, capacitors and inductors follow their temperature coefficients  R(T) = R (1 + tc1 ΔT + tc2 ΔT²)  (extras "tc1", "tc2"),
- MOSFET / JFET transconductance falls as (T/Tn)^-1.5 and their threshold drifts by -2 mV/K.
The temperature is a setting of the circuit: "analysis": {"temp": 85}. Every analysis calls ``use(netlist)`` first."""
import math

from . import components as C

TNOM = 27.0                  # °C
K, Q = 1.380649e-23, 1.602176634e-19
VT0 = 0.025852               # the thermal voltage the program always used (it is the value at TNOM)
EG, XTI = 1.11, 3.0

_state = {"c": TNOM}


def kelvin(c): return c + 273.15


def vt_at(c): return VT0 * kelvin(c) / kelvin(TNOM)


def temp(): return _state["c"]


def set_temp(c):
    """Make `c` °C the temperature of every following calculation (changes the thermal voltage the models read)."""
    c = float(c)
    if not -273.0 < c < 1000.0: raise ValueError("The temperature must be between -273 and 1000 °C.")
    _state["c"] = c
    from . import active, solver
    v = vt_at(c)
    for m in (C, active, solver): m.VT = v


def use(nl):
    """Take the temperature from the circuit's settings (default 27 °C)."""
    t = (nl.analysis or {}).get("temp", TNOM) if isinstance(getattr(nl, "analysis", None), dict) else TNOM
    try: set_temp(t)
    except (TypeError, ValueError): set_temp(TNOM)
    return _state["c"]


def is_factor(n, c, eg=EG, xti=XTI):
    r = kelvin(c) / kelvin(TNOM)
    return r ** (xti / n) * math.exp((r - 1) * eg / (n * vt_at(c)))


def adjust(p):
    """Change a freshly copied part to the current temperature (in place)."""
    c = _state["c"]; d = c - TNOM
    if d == 0: return p
    from . import active as A
    ex = getattr(p, "extra", {})
    if isinstance(p, (C.Resistor, C.Capacitor, C.Inductor)):
        try: tc1, tc2 = float(ex.get("tc1", 0) or 0), float(ex.get("tc2", 0) or 0)
        except ValueError: tc1 = tc2 = 0.0
        if tc1 or tc2: p.value = repr(p.number() * (1 + tc1 * d + tc2 * d * d))
    elif isinstance(p, C.Diode): p.IS = p.IS * is_factor(p.N, c)
    elif isinstance(p, A.BJT):
        v = p.pv("is")
        if v: p.extra["is"] = repr(v * is_factor(1.0, c))
    elif isinstance(p, A.FET):
        r = kelvin(c) / kelvin(TNOM)
        for k in ("kp", "beta"):
            v = p.pv(k) if k in ex else None
            if v: p.extra[k] = repr(v * r ** -1.5)
        v = p.pv("vto") if "vto" in ex else None
        if v is not None: p.extra["vto"] = repr(v - p.pol * 2e-3 * d)
        v = p.pv("is") if "is" in ex else None
        if v: p.extra["is"] = repr(v * is_factor(1.0, c))
    return p
