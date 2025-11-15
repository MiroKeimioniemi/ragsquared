# Testing Guide

This document describes how to run tests, refresh fixtures, run subsets, and debug failures in the AI Auditing System test suite.

## Quick Start

Run all tests:
```bash
make test
```

Run tests without coverage (faster):
```bash
make test-fast
```

Generate coverage report:
```bash
make test-coverage
```

## Test Organization

Tests are organized by domain:

- `tests/api/` - Flask API endpoint tests
- `tests/services/` - Service layer tests (compliance runner, context builder, etc.)
- `tests/pipelines/` - Pipeline CLI tests (chunking, embedding)
- `tests/cli/` - Developer CLI tests
- `tests/db/` - Database model tests
- `tests/reports/` - Report generation tests

## Running Test Subsets

Run tests for a specific module:
```bash
pytest tests/services/test_compliance_runner.py -v
```

Run tests matching a pattern:
```bash
pytest tests/ -k "test_runner" -v
```

Run only unit tests (exclude integration):
```bash
pytest tests/ -m "not integration" -v
```

Run tests in a specific directory:
```bash
pytest tests/api/ -v
```

## Test Fixtures

The test suite uses pytest fixtures defined in `tests/conftest.py`:

- `app` - Flask application instance with ephemeral database
- `client` - Flask test client
- `db_session` - SQLAlchemy session (rolled back after each test)

Each test gets a fresh in-memory SQLite database, so tests are isolated and can run in parallel.

## Debugging Test Failures

### Verbose Output

Run with maximum verbosity:
```bash
pytest tests/ -vvv
```

### Show Print Statements

Use `-s` to see print statements:
```bash
pytest tests/ -s
```

### Run Last Failed Tests

Re-run only the tests that failed last time:
```bash
pytest --lf
```

### Drop into Debugger

Use `--pdb` to drop into the debugger on failures:
```bash
pytest tests/ --pdb
```

### Show Local Variables

Use `-l` to show local variables in tracebacks:
```bash
pytest tests/ -l
```

## Coverage

View coverage report:
```bash
make test-coverage
# Open htmlcov/index.html in your browser
```

Coverage thresholds are not enforced, but aim for >80% coverage on critical paths.

## Type Checking

Run mypy type checking:
```bash
make type-check
```

Note: Some third-party libraries may not have type stubs, so `--ignore-missing-imports` is used.

## Continuous Integration

GitHub Actions runs tests on:
- Python 3.11
- Ubuntu and Windows
- On every push and pull request

See `.github/workflows/tests.yml` for the CI configuration.

## Test Data

Tests use ephemeral in-memory SQLite databases. No persistent test data is required.

For integration tests that need real data, fixtures create sample documents, chunks, and audits as needed.

## Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Fixtures**: Use fixtures for common test data setup
3. **Naming**: Test functions should start with `test_` and be descriptive
4. **Assertions**: Use specific assertions (e.g., `assert x == 5` not `assert x`)
5. **Cleanup**: Tests automatically roll back database changes via fixtures

## Common Issues

### Database Locked

If you see "database is locked" errors, ensure tests are using in-memory databases (they should be by default via fixtures).

### Import Errors

Ensure you're running tests from the project root:
```bash
cd /path/to/Junction25
pytest tests/
```

### Missing Dependencies

Install dev dependencies:
```bash
make dev-install
```

