"""Reads the activity log and the token history and says in plain words what looks wrong and what to try: the 'Findings' view."""
import re

OK, INFO, WARN, BAD = "ok", "info", "warn", "error"


def analyze(entries, cfg, last_request=None, last_response=None):
    """[(level, title, advice)] sorted worst first. Pure function of its inputs, so it is easy to test."""
    out = []; text = "\n".join(e.text for e in entries)
    def add(level, title, advice): out.append((level, title, advice))
    if re.search(r"did not answer|no answer in time|watchdog|gave up", text, re.I):
        add(BAD, "The AI service did not answer in time", "Free models are often queued or overloaded. Press Stop and try again later, pick a different model in the Model box, or use Gemini, Groq or a local Ollama model. Use 'Test model' above to time the model on its own.")
    elif any(e.level == "warn" and "still waiting" in e.text for e in entries):
        add(WARN, "A request was waiting for a long time", "The service was slow to answer. If it keeps happening, choose another model (use 'Test model' to compare).")
    for code, title, advice in (("429", "Quota or rate limit reached (HTTP 429)", "Wait a minute, or choose another model or provider."),
                                ("401", "The key was refused (HTTP 401)", "Paste the key again, complete and without spaces."),
                                ("403", "Access refused (HTTP 403)", "The key's account or project has no access to this model. Create a new key, or try another provider."),
                                ("404", "The model was not found (HTTP 404)", "The model name is wrong or retired. Paste the key again so the live model list is loaded, or type the exact name."),
                                ("400", "The service rejected the request (HTTP 400)", "Turn off 'Limit the AI's hidden thinking' in Settings > AI & Import, or choose another model; the details are under 'Last request'.")):
        if re.search(rf"HTTP {code}\b", text): add(BAD if code != "400" else WARN, title, advice)
    if re.search(r"Could not reach|failed after", text): add(BAD, "The service could not be reached", "Check the internet connection, a proxy or firewall, and that the address is right. 'Test connection' shows which host fails.")
    if last_request and last_request.get("bytes", 0) > 600_000: add(WARN, "The picture sent was large", f"{last_request['bytes'] // 1024:,} KB were sent. Turn on 'Scan pictures on import' (Settings > AI & Import) to shrink it.")
    usage = [e for e in entries if e.source == "tokens" and e.data.get("total")]
    if usage:
        u = usage[-1].data
        if u.get("total", 0) > 15000: add(WARN, f"The last call used {u['total']:,} tokens", "Large calls usually mean hidden 'thinking' or a long instruction: keep 'Limit the AI's hidden thinking' and 'Short answer format' on, and pick the tab yourself instead of Auto.")
        if u.get("output") and u.get("reasoning", 0) > 0.5 * u["output"]: add(WARN, "Most output tokens were hidden thinking", f"{u['reasoning']:,} of {u['output']:,} output tokens. Use a non-thinking model, or keep the thinking limit on.")
    if cfg.get("provider", "").startswith("OpenRouter") and "openrouter/free" in str((cfg.get("models") or {}).get("OpenRouter (free models)", "")):
        add(INFO, "OpenRouter's free router picks a different model each time", "Choose a specific free model that accepts pictures in the Model box for predictable speed.")
    if not cfg.get("scan_on", True): add(INFO, "Scan on import is off", "The original picture is sent: larger, so slower and more tokens.")
    if not out: add(OK, "No problems found", "Nothing in the log looks wrong. If something is slow, run 'Test model' and watch the seconds it takes.")
    order = {BAD: 0, WARN: 1, INFO: 2, OK: 3}
    return sorted(out, key=lambda r: order[r[0]])
