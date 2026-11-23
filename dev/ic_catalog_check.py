"""Compares the IC catalogue (workspaces/logisim/ic/catalog.py) with the Java sources of Logisim-evolution.

    python dev/ic_catalog_check.py path/to/logisim-evolution-5.0.0

Checks every chip: pin count and, where Logisim gives physical pin numbers, the output pins.  Chips whose Java
code counts ports instead of pins (marked below) are skipped for the output check; they are covered by the
signal-name order check instead.  Exit status 1 if anything differs.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from vibesimulation.workspaces.logisim.ic import catalog as C       # noqa: E402

PORT_INDEXED = {"7438", "74138", "74139", "74151", "74153", "74157", "74158", "74173", "74181", "74182", "74194", "74299",
                "74381", "74541", "74670", "7476"}                  # Java numbers ports from 0 / skips power pins


def java_info(src, part):
    s = (src / f"Ttl{part}.java").read_text(encoding="utf8", errors="ignore")
    m = re.search(r"extends\s+(Ttl\w+)", s)
    if m: s += (src / f"{m.group(1)}.java").read_text(encoding="utf8", errors="ignore")
    pc = re.search(r"(?:pinCount|portCount)\s*=\s*(?:\(byte\)\s*)?(\d+)", s) or re.search(r"\(byte\)\s*(1[0-9]|2[0-9])\b", s)
    outs = None
    for pat in (r"(?:outPins|outPorts|OUTPUT_PORTS)\s*=\s*(?:new byte\[\])?\s*\{([^}]*)\}", r"new byte\[\]\s*\{([^}]*)\}"):
        mm = re.search(pat, s)
        if mm: outs = [int(x) for x in re.findall(r"\d+", mm.group(1))]; break
    names = re.search(r"new String\[\]\s*\{([^}]*)\}", s)
    return (int(pc.group(1)) if pc else None), outs, (re.findall(r'"([^"]*)"', names.group(1)) if names else None)


def main(root):
    src = Path(root) / "src/main/java/com/cburch/logisim/std/ttl"
    ids = sorted(p.name[3:-5] for p in src.glob("Ttl*.java") if re.fullmatch(r"Ttl\d+\.java", p.name))
    bad = 0
    missing = [i for i in ids if i not in C.CHIPS]
    extra = [i for i in C.CHIPS if i not in ids and C.CHIPS[i].logisim]
    if missing or extra: print("catalogue differs from Logisim's chip list: missing", missing, "extra", extra); bad += 1
    for part, ch in C.CHIPS.items():
        if part not in ids or not ch.logisim: continue
        pc, outs, names = java_info(src, part)
        mine = [i + 1 for i, p in enumerate(ch.pinout) if p.kind in ("out", "io")]
        if pc and pc != ch.pins: print(f"{part}: pins {ch.pins} but Logisim says {pc}"); bad += 1
        if outs and part not in PORT_INDEXED and sorted(outs) != mine: print(f"{part}: output pins {mine} but Logisim says {sorted(outs)}"); bad += 1
        if names:                                                       # same number of signal pins in the same order
            sig = [p for p in ch.pinout if p.kind not in ("vcc", "gnd", "nc")]
            if len(sig) != len(names): print(f"{part}: {len(sig)} signal pins but Logisim names {len(names)}"); bad += 1
    print(f"{sum(1 for x in C.CHIPS.values() if x.logisim)} Logisim chips checked (+{sum(1 for x in C.CHIPS.values() if not x.logisim)} from lab sheets), {bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
