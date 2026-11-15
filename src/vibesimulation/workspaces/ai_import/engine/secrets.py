"""Optional safe storage of API keys in the operating system's keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service).

Needs the optional ``keyring`` package. Without it nothing is stored and the key must be typed (or set as an environment variable)
each time. Keys are never written to the settings JSON file."""
SERVICE = "VibeSimulation"


def get_key(provider):
    try:
        import keyring
        return keyring.get_password(SERVICE, provider) or ""
    except Exception:
        return ""


def set_key(provider, key):
    """Returns True when the key was stored."""
    try:
        import keyring
        keyring.set_password(SERVICE, provider, key)
        return True
    except Exception:
        return False


def delete_key(provider):
    try:
        import keyring
        keyring.delete_password(SERVICE, provider)
    except Exception:
        pass


def available():
    """True when the optional ``keyring`` package is installed."""
    try:
        import keyring  # noqa: F401
        return True
    except Exception:
        return False
