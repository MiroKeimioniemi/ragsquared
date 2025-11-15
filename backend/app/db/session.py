from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

_engine: Engine | None = None
_session_factory: scoped_session | None = None


def init_engine(database_url: str) -> Engine:
    """Initialize (or retrieve) the global SQLAlchemy engine."""
    global _engine, _session_factory

    if _engine is not None and str(_engine.url) == database_url:
        return _engine

    if _session_factory is not None:
        _session_factory.remove()

    _engine = create_engine(database_url, future=True)
    _session_factory = scoped_session(
        sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    )
    return _engine


def get_session() -> Session:
    if _session_factory is None:
        raise RuntimeError("Database engine has not been initialized.")
    return _session_factory()


def shutdown_session(_: object | None = None) -> None:
    if _session_factory is not None:
        _session_factory.remove()


