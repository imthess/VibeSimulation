"""The Activity report as Markdown text (and the same text drawn into a PDF by ``pdf.py``). Never contains API keys."""
import json
import time

from vibesimulation.common import activity
from vibesimulation.workspaces.activity.core import environment, findings
from vibesimulation.workspaces.ai_import.core import usage


def build(cfg, entries=None):
    entries = activity.LOG.all() if entries is None else entries
    L = ["# VibeSimulation activity report", "", f"Created {time.strftime('%Y-%m-%d %H:%M:%S')}  ·  {len(entries)} log lines", ""]
    L += ["## Findings", ""]
    for level, title, advice in findings.analyze(entries, cfg, activity.LOG.last_request, activity.LOG.last_response): L.append(f"- **{title}** ({level}): {advice}")
    run = activity.LOG.running()
    L += ["", "## Running now", ""] + ([f"- {n}: {s:.0f} s so far" for n, s in run] or ["- nothing"])
    L += ["", "## System", ""] + [f"- {k}: {v}" for k, v in environment.system_info()]
    L += ["", "## AI settings", ""] + [f"- {k}: {v}" for k, v in environment.ai_settings(cfg)]
    log = cfg.get("ai_usage", []); t = usage.totals(log)
    L += ["", "## Token usage", "", f"{t['calls']} calls, {t['total']:,} tokens ({t['prompt']:,} in, {t['output']:,} out, {t['reasoning']:,} thinking)", ""]
    for e in log[-15:]: L.append(f"- {usage.when(e)}  {e.get('what', '')}  {e.get('provider', '')}  {e.get('model', '')}: {e.get('prompt', 0):,} in, {e.get('output', 0):,} out, {e.get('reasoning', 0):,} thinking")
    for title, d in (("Last request", activity.LOG.last_request), ("Last response", activity.LOG.last_response)):
        L += ["", f"## {title}", ""] + (["```json", json.dumps(d, indent=1, default=str), "```"] if d else ["none yet"])
    L += ["", "## Log", "", "```"] + [f"{e.clock()}  {e.level.upper():5}  {e.source:7}  {e.text}" for e in entries] + ["```", ""]
    return activity.redact("\n".join(L))
