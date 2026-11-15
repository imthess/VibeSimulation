"""API-key detection (no window): which provider a pasted key belongs to."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vibesimulation.workspaces.ai_import.engine import PROVIDERS
from vibesimulation.workspaces.ai_import.engine.key_detect import RULES, clean_key, detect_provider
ok = True
def chk(n, c):
    global ok; print(("ok  " if c else "FAIL"), n); ok = ok and bool(c)
cases = {"AIzaSyA1234567890abcdefghijklmnopqrstuv": "Gemini (free tier)", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123": "Claude (paid API)",
         "sk-or-v1-abcdefghijklmnopqrstuvwxyz0123456789": "OpenRouter (free models)", "gsk_abcdefghijklmnopqrstuvwxyz0123456789": "Groq (free tier)",
         "sk-proj-abcdefghijklmnopqrstuvwxyz012345": "OpenAI (paid API)", "sk-abcdefghijklmnopqrstuvwxyz012345": "OpenAI (paid API)",
         "Bearer AIzaSyA1234567890abcdefghijklmnopqrstuv": "Gemini (free tier)", "\"gsk_abcdefghijklmnopqrstuvwxyz0123456789\"": "Groq (free tier)",
         "hello": None, "": None, None: None, "sk-short": None, "AIza": None}
for k, want in cases.items(): chk(f"{str(k)[:28]!r} -> {want}", detect_provider(k) == want)
chk("every rule names a real provider", all(n in PROVIDERS for n, _ in RULES))
chk("specific prefixes are not taken by the general OpenAI rule", detect_provider("sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123") != "OpenAI (paid API)" and detect_provider("sk-or-v1-abcdefghijklmnopqrstuvwxyz0123456789") != "OpenAI (paid API)")
chk("clean_key removes spaces, quotes and Bearer", clean_key('  "Bearer abc"  ') == "abc" or clean_key("  Bearer abc ") == "abc")
print("ALL OK" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
