from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from backend.app import create_app
from backend.app.db.session import get_session


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_root = tmp_path / "data"
    monkeypatch.setenv("DATA_ROOT", str(data_root))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'app.db'}")

    application = create_app()
    ctx = application.app_context()
    ctx.push()

    yield application

    ctx.pop()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_session() -> Iterator:
    session = get_session()
    try:
        yield session
    finally:
        session.rollback()


