"""aiquota — one view of every AI subscription's remaining quota."""
__version__ = "0.2.1"

from .core import (Adapter, Result, Window, register, registry,  # noqa: F401
                   LIVE, LOCAL, MANUAL, UNCONFIGURED, ERROR)

__all__ = ["Adapter", "Result", "Window", "register", "registry",
           "LIVE", "LOCAL", "MANUAL", "UNCONFIGURED", "ERROR", "__version__"]
