"""The fine-tuning tools: dataset generator is valid, the scorer accepts true answers and rejects wrong ones, evaluate.py runs end to end (fake model)."""
import sys, os, json, random, tempfile, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src")); sys.path.insert(0, os.path.join(HERE, "finetune"))
from vibesimulation.workspaces.logisim.components import load_all; load_all()
import circuits_analog, circuits_digital, score as S, evaluate as E
ok = True
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
import vibesimulation.workspaces.logisim.core.serializer as serializer
import vibesimulation.workspaces.multisim.core.netlist as anet
bad = 0
for i in range(300):
    t = circuits_digital.generate(random.Random(i)); c, e = serializer.parse(t)
    if e or c is None or c.order() is None or not c.outputs: bad += 1
chk("300 random digital circuits parse, have outputs and no loops", bad == 0)
bad = sum(bool(anet.parse(circuits_analog.generate(random.Random(i)))[1]) for i in range(300))
chk("300 random analog circuits parse", bad == 0)
for kind, gen in (("digital", circuits_digital.generate), ("analog", circuits_analog.generate)):
    ts = [gen(random.Random(i)) for i in range(40)]
    chk(f"{kind}: the true answer scores as correct", all(S.score(t, json.dumps(t))[2] for t in ts))
    chk(f"{kind}: an answer wrapped in text and code fences still scores", all(S.score(t, "Here:\n```json\n" + json.dumps(t) + "\n```")[2] for t in ts))
    chk(f"{kind}: nonsense scores as wrong", not any(S.score(t, "I cannot see a circuit")[2] for t in ts))
d = circuits_digital.generate(random.Random(5)); d2 = json.loads(json.dumps(d)); g = d2["gates"][0]; g["type"] = "OR" if g["type"] != "OR" else "AND"
chk("digital: a changed gate type is caught", not S.score(d, json.dumps(d2))[2] or S.score(d, json.dumps(d2))[1]["behaviour"])
# structure-different but equal behaviour (A AND B written as NOT(NAND)) counts as correct
t = {"kind": "digital", "inputs": ["A", "B"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "AND", "in": ["A", "B"], "out": "Y"}]}
p = {"kind": "digital", "inputs": ["A", "B"], "outputs": ["Y"], "gates": [{"id": "g1", "type": "NAND", "in": ["A", "B"], "out": "n1"}, {"id": "g2", "type": "NOT", "in": ["n1"], "out": "Y"}]}
r = S.score(t, json.dumps(p)); chk("digital: same behaviour, different gates = correct (gate_types False)", r[2] and not r[1]["gate_types"])
w = json.loads(json.dumps(t)); w["gates"][0]["type"] = "OR"; chk("digital: wrong behaviour caught", not S.score(t, json.dumps(w))[2])
a = circuits_analog.generate(random.Random(11)); a2 = json.loads(json.dumps(a))
ren = {n: ("0" if n == "0" else "x" + n) for p_ in a2["components"] for n in p_["nodes"]}
for p_ in a2["components"]: p_["nodes"] = [ren[n] for n in p_["nodes"]]
chk("analog: renamed nets are still correct", S.score(a, json.dumps(a2))[2])
a3 = json.loads(json.dumps(a)); r_ = next(p_ for p_ in a3["components"] if p_["type"] == "Resistor"); r_["value"] = "123k"
chk("analog: a wrong value is caught", not S.score(a, json.dumps(a3))[2])
a4 = json.loads(json.dumps(a)); p_ = a4["components"][1]; p_["nodes"] = p_["nodes"][::-1]
chk("analog: wiring or polarity flip is caught when it changes the circuit", S.score(a, json.dumps(a4))[2] == (S._wl(anet.parse(a4)[0]) == S._wl(anet.parse(a)[0])))
tmp = tempfile.mkdtemp()
rc = subprocess.run([sys.executable, os.path.join(HERE, "finetune", "make_dataset.py"), tmp, "--train", "6", "--test", "6", "--seed", "2"], capture_output=True, text=True).returncode
chk("make_dataset.py runs", rc == 0 and len(os.listdir(os.path.join(tmp, "images"))) == 12)
rows = [json.loads(l) for l in open(os.path.join(tmp, "test.jsonl"))]
tr = [json.loads(l) for l in open(os.path.join(tmp, "train.jsonl"))]
chk("train rows are chat examples whose answer is valid JSON", all(json.loads(r["messages"][1]["content"][0]["text"])["kind"] in ("digital", "analog") for r in tr))
answers = {r["image"]: json.dumps(r["truth"]) for r in rows}
png2row = {open(os.path.join(tmp, r["image"]), "rb").read(): r["image"] for r in rows}
res = E.run(rows, lambda png: answers[png2row[png]], tmp, log=lambda *a: None)
chk("evaluate.run with a perfect fake model: 100%", all(r["correct"] for r in res))
res = E.run(rows, lambda png: "no circuit", tmp, log=lambda *a: None)
chk("evaluate.run with a useless fake model: 0%", not any(r["correct"] for r in res) and "0/" in E.summary(res))
print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
