"""Tools that find out why something is slow or failing. Each runs in a background thread and writes what it finds to the activity log."""
import threading
import time

from vibesimulation.common import activity
from vibesimulation.workspaces.ai_import.core import autodetect
from vibesimulation.workspaces.ai_import.core.providers import PROVIDERS, chat_model


def _thread(fn, *a):
    threading.Thread(target=fn, args=a, daemon=True).start()


def test_connection(provider, key, base):
    """Can the service be reached, is the key accepted, and how fast is its model list? Writes the result to the log."""
    def run():
        activity.log("tool", f"Test connection: {provider}", "info"); t0 = time.time()
        found = autodetect.discover(key, provider, {provider: base} if base else None, PROVIDERS)
        dt = time.time() - t0
        if found.accepted: activity.log("tool", f"Connection OK in {dt:.1f} s: {len(found.models)} live models, best {found.best or '-'}", "ok")
        elif found.accepted is False: activity.log("tool", f"The service refused the key: {found.message}", "error")
        else: activity.log("tool", f"Could not reach or check the service after {dt:.1f} s: {found.message or 'no answer'}", "error")
    _thread(run)


def test_model(provider, model, key, base):
    """Ask the chosen model one tiny text question: shows how long the model itself takes, without any picture."""
    def run():
        activity.log("tool", f"Test model: {provider} / {model} (text only: 'Reply with the single word OK')", "info"); t0 = time.time()
        try:
            text = chat_model(provider, model, key, "Answer as briefly as possible.", "Reply with the single word OK.", base, False)
            dt = time.time() - t0
            activity.log("tool", f"The model answered in {dt:.1f} s: {text.strip()[:60]!r}", "ok" if dt < 20 else "warn")
            if dt >= 20: activity.log("tool", "That is slow for one word: the model is busy or heavy. A picture will take much longer. Choose another model.", "warn")
        except Exception as e:
            activity.log("tool", f"The model failed after {time.time() - t0:.1f} s: {str(e)[:300]}", "error")
    _thread(run)
