"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

# Context variable for request/trace IDs
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
audit_id_var: ContextVar[str | None] = ContextVar("audit_id", default=None)
chunk_id_var: ContextVar[str | None] = ContextVar("chunk_id", default=None)


def add_context_fields(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Add context fields (request_id, audit_id, chunk_id) to log events."""
    request_id = request_id_var.get()
    audit_id = audit_id_var.get()
    chunk_id = chunk_id_var.get()
    
    if request_id:
        event_dict["request_id"] = request_id
    if audit_id:
        event_dict["audit_id"] = audit_id
    if chunk_id:
        event_dict["chunk_id"] = chunk_id
    
    return event_dict


def configure_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """
    Configure structlog with processors and output format.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON; if False, output human-readable format
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    
    # Build processors
    processors = [
        structlog.contextvars.merge_contextvars,
        add_context_fields,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured structlog logger."""
    return structlog.get_logger(name)


def set_request_id(request_id: str) -> None:
    """Set the request ID in the current context."""
    request_id_var.set(request_id)


def set_audit_id(audit_id: str) -> None:
    """Set the audit ID in the current context."""
    audit_id_var.set(audit_id)


def set_chunk_id(chunk_id: str) -> None:
    """Set the chunk ID in the current context."""
    chunk_id_var.set(chunk_id)


def clear_context() -> None:
    """Clear all context variables."""
    request_id_var.set(None)
    audit_id_var.set(None)
    chunk_id_var.set(None)

