"""
Shim package that exposes worker entrypoints under the top-level `workers.*`
namespace so they can be invoked with `python -m workers.<name>`.
"""

from backend.workers.extract import app  # re-export for discovery

__all__ = ["app"]


