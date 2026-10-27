"""Update check (against a local server), recovery file, version compare."""
import sys, os, json, threading, tempfile, time, http.server
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.components import load_all; load_all()
from vibesimulation.product import updates as U
from vibesimulation.product.recovery import Recovery
bad = 0
def ok(c, m):
    global bad
    if not c: bad += 1; print("FAIL", m)
    else: print("ok  ", m)
ok(U.parse_version("v1.2.10-beta") == (1, 2, 10) and U.parse_version("x") == (), "parse")
ok(U.is_newer("1.10.0", "1.9.9") and not U.is_newer("1.1", "1.2.0") and U.is_newer("2", "1.9") and not U.is_newer("abc", "1.0"), "compare")
ok(U.normalize({"tag_name": "v2.0.1", "html_url": "https://x/y", "body": "n"}) == {"version": "2.0.1", "url": "https://x/y", "notes": "n"}, "github shape")
try: U.normalize({"version": "?"}); ok(False, "bad shape refused")
except ValueError: ok(True, "bad shape refused")
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"version": "9.0.0", "url": "https://example.org/dl", "notes": "hi"}).encode() if self.path == "/ok" else b"not json"
        self.send_response(200); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start(); port = srv.server_address[1]
newer, info = U.check(f"http://127.0.0.1:{port}/ok", "1.2.0"); ok(newer and info["version"] == "9.0.0", "check finds a newer version")
try: U.check(f"http://127.0.0.1:{port}/bad", "1.2.0"); ok(False, "bad answer")
except ValueError: ok(True, "non-JSON answer is an error")
try: U.check("ftp://x", "1"); ok(False, "scheme")
except ValueError: ok(True, "only http(s)")
got = []; U.check_async(f"http://127.0.0.1:{port}/ok", "1.2.0", lambda *a: got.append(a), lambda f: f())
for _ in range(50):
    if got: break
    time.sleep(0.05)
ok(got and got[0][0] is True, "async check calls back")
# recovery with a fake shell
from vibesimulation.core.document import Document
from vibesimulation.analog.document import AnalogDocument
from vibesimulation.vlsi.document import VlsiDocument
class Sh: pass
sh = Sh(); sh.doc, sh.adoc, sh.vdoc = Document(), AnalogDocument(), VlsiDocument(); sh.doc.load_sample(); sh.adoc.load_sample(); sh.vdoc.load_sample()
p = os.path.join(tempfile.mkdtemp(), "rec.json"); r = Recovery(p); r.start(sh)
ok(not r.save(sh) and r.pending() is None, "nothing changed: nothing written")
sh.adoc.load_text(json.dumps({"components": [{"id": "V1", "type": "V", "value": 3, "nodes": ["a", "0"]}, {"id": "R1", "type": "R", "value": 100, "nodes": ["a", "0"]}]}))
sh.vdoc.new_blank("module t(input a, output y);\n assign y = ~a;\nendmodule\n"); sh.vdoc.set_testbench("module tb; initial $finish; endmodule\n")
ok(r.save(sh) and r.pending() is not None, "change is written")
ok(not r.save(sh), "same state is not written twice")
data = r.pending(); sh2 = Sh(); sh2.doc, sh2.adoc, sh2.vdoc = Document(), AnalogDocument(), VlsiDocument()
done = Recovery.restore(sh2, data)
ok(set(done) == {"logisim", "multisim", "vlsi"}, f"restored {done}")
ok(sh2.adoc.valid and "V1" in sh2.adoc.text and sh2.vdoc.cur == "t" and "module tb" in sh2.vdoc.tb_text and sh2.doc.valid, "restored content")
r.clear(); ok(r.pending() is None, "clean exit removes the file")
open(p, "w").write("garbage"); ok(r.pending() is None, "a damaged file is ignored")
sys.exit(1 if bad else 0)
