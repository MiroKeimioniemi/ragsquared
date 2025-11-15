from __future__ import annotations

from typing import Any, Protocol


class AnalysisClient(Protocol):
    """Protocol describing the interface required by the compliance runner."""

    def analyze(self, chunk, context) -> dict[str, Any]:  # pragma: no cover - typing aid
        ...

