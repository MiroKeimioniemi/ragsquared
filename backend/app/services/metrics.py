"""Metrics collection and emission for monitoring."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MetricsCollector:
    """Collects and emits metrics for monitoring."""
    
    chunks_processed: int = 0
    chunks_per_minute: float = 0.0
    retry_count: int = 0
    token_usage: int = 0
    start_time: float = field(default_factory=time.time)
    last_emission: float = field(default_factory=time.time)
    emission_interval: float = 60.0  # Emit metrics every 60 seconds
    
    def record_chunk_processed(self, tokens_used: int = 0) -> None:
        """Record a processed chunk and update metrics."""
        self.chunks_processed += 1
        self.token_usage += tokens_used
        
        # Update chunks per minute
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            self.chunks_per_minute = (self.chunks_processed / elapsed) * 60
        
        # Emit metrics if interval has passed
        if time.time() - self.last_emission >= self.emission_interval:
            self.emit_metrics()
    
    def record_retry(self) -> None:
        """Record a retry attempt."""
        self.retry_count += 1
    
    def emit_metrics(self) -> None:
        """Emit current metrics to logs."""
        metrics = {
            "chunks_processed": self.chunks_processed,
            "chunks_per_minute": round(self.chunks_per_minute, 2),
            "retry_count": self.retry_count,
            "token_usage": self.token_usage,
            "elapsed_seconds": round(time.time() - self.start_time, 2),
        }
        logger.info("metrics", **metrics)
        self.last_emission = time.time()
    
    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics as a dictionary."""
        elapsed = time.time() - self.start_time
        return {
            "chunks_processed": self.chunks_processed,
            "chunks_per_minute": round(self.chunks_per_minute, 2) if elapsed > 0 else 0.0,
            "retry_count": self.retry_count,
            "token_usage": self.token_usage,
            "elapsed_seconds": round(elapsed, 2),
        }


# Global metrics collector (can be replaced with per-audit collectors)
_global_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    return _global_metrics


def reset_metrics() -> None:
    """Reset global metrics (useful for testing)."""
    global _global_metrics
    _global_metrics = MetricsCollector()

