"""Apps Factory licences (stdlib consumers need no signing dependencies)."""
from importlib import import_module
from .guard import ClockGuard

__version__ = "0.4.1"
__all__ = ["ALG", "FORMAT", "PURPOSES", "Result", "ClockGuard", "canonical", "clock_rolled_back", "codes", "fingerprint",
           "generate_keypair", "issue", "key_id", "verify", "__version__"]


def __getattr__(name):
    if name == 'codes':
        value = import_module('.codes', __name__)
    elif name in __all__ and name not in {'ClockGuard', '__version__'}:
        value = getattr(import_module('.core', __name__), name)
    else:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    globals()[name] = value
    return value
