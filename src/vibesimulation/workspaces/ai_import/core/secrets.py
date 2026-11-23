"""Remembering API keys between sessions.

1. The operating system's keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service) when the optional ``keyring`` package works.
2. Otherwise a small private file in your home folder (``~/.vibesimulation-keys``, readable only by you). It is only lightly scrambled, not encrypted:
   anyone who can read your files can recover the keys, so use the keychain (pip install keyring) on a shared computer.
Keys are never written to the settings JSON file."""
import base64
import json
import os
from pathlib import Path

SERVICE = "VibeSimulation"
FILE = Path.home() / ".vibesimulation-keys"


def _read():
    try: return {k: base64.b64decode(v).decode() for k, v in json.loads(FILE.read_text(encoding="utf-8")).items()}
    except Exception: return {}


def _write(d):
    try:
        FILE.write_text(json.dumps({k: base64.b64encode(v.encode()).decode() for k, v in d.items()}), encoding="utf-8")
        os.chmod(FILE, 0o600)
        return True
    except Exception:
        return False


def get_key(provider):
    try:
        import keyring
        v = keyring.get_password(SERVICE, provider)
        if v: return v
    except Exception:
        pass
    return _read().get(provider, "")


def set_key(provider, key):
    """Store a key; returns where it went: 'keychain', 'file' or '' (not stored)."""
    try:
        import keyring
        keyring.set_password(SERVICE, provider, key)
        return "keychain"
    except Exception:
        pass
    d = _read(); d[provider] = key
    return "file" if _write(d) else ""


def delete_key(provider):
    try:
        import keyring
        keyring.delete_password(SERVICE, provider)
    except Exception:
        pass
    d = _read()
    if d.pop(provider, None) is not None: _write(d)


def available():
    """True when the optional ``keyring`` package is installed."""
    try:
        import keyring  # noqa: F401
        return True
    except Exception:
        return False
