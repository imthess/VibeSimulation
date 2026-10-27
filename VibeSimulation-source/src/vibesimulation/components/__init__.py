"""Importing this package registers every component with the ComponentRegistry."""
import importlib
import pkgutil

from .registry import ComponentRegistry


def load_all():
    for sub in ("gates", "wiring", "plexers", "arithmetic", "io", "memory"):
        pkg = importlib.import_module(f"{__name__}.{sub}")
        for m in pkgutil.iter_modules(pkg.__path__):
            importlib.import_module(f"{pkg.__name__}.{m.name}")


load_all()
__all__ = ["ComponentRegistry"]
