"""One request to the AI, from the user's words to the changed document.

The network call runs in a thread; everything else (reading the answer, checking it, changing the document) happens on the window's thread when
the window calls ``poll()``. An answer that does not compile / validate is sent back to the model together with the problems found (up to
``MAX_TRIES`` calls in all), so most small mistakes of the model repair themselves before the user ever sees them."""
import queue
import threading

from vibesimulation.workspaces.ai_import.core import PROVIDERS, chat_model, explain_error
from vibesimulation.common import activity
from vibesimulation.workspaces.ai_import.core import profile, usage
from vibesimulation.workspaces.ai_import.core.autodetect import call_with_fallback
from vibesimulation.workspaces.ai_import.core.key_detect import clean_key
class NeedSetup(Exception):
    """The AI service is not set up yet (no key, no model); the message says what to do."""


class Session:
    MAX_TRIES = 3

    def __init__(self, shell):
        self.sh = shell; self.q = queue.Queue(); self.token = 0; self.job = None

    @property
    def busy(self): return self.job is not None

    # ---- the service chosen on the Import & AI page (one setting for the whole app)
    def config(self):
        cfg = self.sh.pages["import"].view.ctx.cfg
        if profile.enabled(cfg):                                  # Settings > AI & Import > a different AI for the AI button
            name, model, base = profile.get(cfg); prov = PROVIDERS[name]; key = profile.key(name, prov.env)
            if prov.env and not key: raise NeedSetup(f"The AI button uses {name}, but its key is missing. Set it in Settings > AI & Import.")
            return name, model or prov.models[0], key, base or prov.base
        v = self.sh.pages["import"].view; name = v.prov.get(); prov = PROVIDERS[name]
        model, key, base = v.model.get().strip(), clean_key(v.key.get()), v.base.get().strip()
        if not model: raise NeedSetup("Choose a model first (the gear button).")
        if prov.env and not key: raise NeedSetup(f"Paste your API key for {name} (the gear button).\n{prov.help}")
        return name, model, key, base

    def start(self, target, request, mode="edit"):
        name, model, key, base = self.config()
        self.token += 1
        self.job = dict(target=target, request=request, mode=mode, current=target.current(), tries=1, bad=None, errors=None, cfg=(name, model, key, base), tok=self.token)
        self._send(); return model

    def cancel(self): self.token += 1; self.job = None

    def _send(self):
        j = self.job; t = j["target"]; name, model, key, base = j["cfg"]; tok = j["tok"]
        user = t.user_fix(j["request"], j["current"], j["bad"], j["errors"]) if j["errors"] else t.user(j["request"], j["current"], j["mode"])
        system = t.system(j["mode"]); want_json = j["mode"] == "edit" and not t.code
        def work():
            usage.context("assistant"); activity.secret(key)
            jid = activity.LOG.begin(f"AI button: {name} / {model}", source="assistant")
            activity.log("assistant", f"request to {name}, model {model}, mode {j['mode']}, try {j['tries']}: {user[:120]!r}")
            try:
                text, used = call_with_fallback(name, model, key, base, lambda m: chat_model(name, m, key, system, user, base, want_json), PROVIDERS)
                if used != model: self.q.put((tok, "model", used))
                activity.LOG.end(jid, True, f"answer received ({len(text):,} characters)"); self.q.put((tok, "reply", text))
            except Exception as e: activity.LOG.end(jid, False, str(e).split("\n")[0][:200]); self.q.put((tok, "err", str(e) + explain_error(name, str(e))))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        """Events since the last call: ("status", text) | ("done", info dict) | ("error", text)."""
        out = []
        while True:
            try: tok, kind, val = self.q.get_nowait()
            except queue.Empty: return out
            j = self.job
            if j is None or tok != j["tok"] or tok != self.token: continue          # cancelled or superseded
            if kind == "model":                                                     # the chosen model no longer exists: a live one was used
                if not profile.enabled(self.sh.pages["import"].view.ctx.cfg): self.sh.pages["import"].view.model.set(val)
                j["cfg"] = (j["cfg"][0], val, *j["cfg"][2:]); out.append(("status", f"The chosen model is not available; using {val} instead.")); continue
            if kind == "err": self.job = None; out.append(("error", "Failed: " + val)); continue
            t = j["target"]
            if j["mode"] == "ask": self.job = None; out.append(("done", dict(kind="ask", text=val.strip() or "(no answer)", key=t.key))); continue
            try: code = t.extract(val); errors = t.check(code)
            except ValueError as e: code, errors = val, [str(e)]
            if errors:
                if j["tries"] >= self.MAX_TRIES:
                    self.job = None; out.append(("error", "The AI's answer could not be used, even after it was asked to fix it:\n" + "\n".join("- " + e for e in errors[:5]))); continue
                j.update(tries=j["tries"] + 1, bad=code, errors=errors); self._send()
                out.append(("status", f"The answer had {len(errors)} problem{'s' if len(errors) != 1 else ''}; asking the AI to fix it (try {j['tries']} of {self.MAX_TRIES})…")); continue
            old = j["current"]
            if code.strip() == old.strip(): self.job = None; out.append(("done", dict(kind="same", text="The AI left it unchanged. Try describing the change more precisely.", key=t.key))); continue
            try: t.apply(code)
            except ValueError as e: self.job = None; out.append(("error", f"The change could not be applied: {e}")); continue
            self.job = None; out.append(("done", dict(kind="edit", text=t.summary(old, code), key=t.key, tries=j["tries"])))
