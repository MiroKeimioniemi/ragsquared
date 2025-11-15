VENV_DIR := .venv

ifeq ($(OS),Windows_NT)
	VENV_PY := py -3.11
	PYTHON_BIN := $(VENV_DIR)/Scripts/python.exe
	PIP_BIN := $(VENV_DIR)/Scripts/pip.exe
else
	VENV_PY := python3.11
	PYTHON_BIN := $(VENV_DIR)/bin/python
	PIP_BIN := $(VENV_DIR)/bin/pip
endif

FLASK := $(PYTHON_BIN) -m flask

.PHONY: dev-install dev-up ensure-dirs db-upgrade lint test clean demo-status

$(PYTHON_BIN):
	$(VENV_PY) -m venv $(VENV_DIR)
	$(PIP_BIN) install --upgrade pip

dev-install: $(PYTHON_BIN)
	$(PIP_BIN) install -e .[dev]

ensure-dirs: dev-install
	$(PYTHON_BIN) backend/scripts/ensure_dirs.py

dev-up: ensure-dirs
	$(FLASK) --app backend.app --debug run

db-upgrade: dev-install
	$(PYTHON_BIN) -m alembic -c alembic.ini upgrade head

lint: dev-install
	$(PYTHON_BIN) -m ruff check backend tests
	$(PYTHON_BIN) -m black --check backend tests

test: dev-install
	$(PYTHON_BIN) -m pytest tests/ -v --cov=backend --cov-report=term-missing --cov-report=html

test-fast: dev-install
	$(PYTHON_BIN) -m pytest tests/ -v

test-coverage: dev-install
	$(PYTHON_BIN) -m pytest tests/ --cov=backend --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/index.html"

type-check: dev-install
	$(PYTHON_BIN) -m mypy backend --ignore-missing-imports --no-strict-optional

clean:
	@if exist $(VENV_DIR) (rmdir /s /q $(VENV_DIR)) || true

demo-status: dev-install
	@echo "Demo CLI status command (requires an audit ID):"
	@echo "Usage: $(PYTHON_BIN) cli.py status <audit-id> [--poll] [--json]"

demo: dev-install
	$(PYTHON_BIN) -m scripts.demo

