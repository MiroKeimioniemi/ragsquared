# AI-Assisted Auditing Backend

Hackathon-ready backend for the EASA Part-145 compliance assistant described in `AI_Auditing_System_Design.md`. The goal of this repo is to provide a minimal-yet-extensible Flask application that future tracks can build upon (document ingestion, agent orchestration, reporting, demo polish).

## Features

- Flask app factory with `/healthz` and `/` endpoints.
- `pyproject.toml` with the LangChain/OpenRouter/Chroma stack described in the design doc.
- Makefile helpers (`make dev-up`, `make dev-install`, `make lint`, `make test`).
- Alembic-powered database migrations for documents, chunks, embedding jobs, audits, flags, and citations.
- `.env` management via `python-dotenv`.
- Directory scaffolding for uploads, processed assets, logs, and vector stores.
- Utility scripts for environment validation and data directory creation.
- Deterministic context builder + sequential compliance runner CLI for executing audits.
- Markdown/PDF report generator backed by stored flags & citations.

## Quickstart

### Automated Setup (Recommended)

```bash
# Run the setup script
python setup.py

# Edit .env file and add your API keys
# Then start the application
make dev-up
```

### Manual Setup

```bash
# 1. Create virtual environment and install dependencies
make dev-install

# 2. Create .env file from template
# Copy .env.example to .env and edit with your API keys
cp .env.example .env
# Edit .env and add:
#   - OPENROUTER_API_KEY (required)
#   - OPENAI_API_KEY (if using OpenAI embeddings)
#   - Or use EMBEDDING_MODEL=all-mpnet-base-v2 for free embeddings

# 3. Initialize database
make db-upgrade

# 4. Verify environment
python backend/scripts/check_env.py

# 5. Start the application
make dev-up
```

The application will be available at http://localhost:5000

**For detailed setup instructions, see [MVP_SETUP_GUIDE.md](MVP_SETUP_GUIDE.md)**

## Environment Variables

**Required Setup:**

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API keys:
   - **LLM API Key** (REQUIRED) - Choose one:
     - Featherless: `LLM_API_KEY=rc_...` (get from https://featherless.ai/)
     - OpenRouter: `OPENROUTER_API_KEY=sk-or-v1-...` (get from https://openrouter.ai/keys)
   - **OPENAI_API_KEY** (REQUIRED if using OpenAI embeddings)
   - Or use free embeddings: Set `EMBEDDING_MODEL=all-mpnet-base-v2` (no API key needed)

### Key Environment Variables

| Variable | Required | Purpose | Default |
| --- | --- | --- | --- |
| `LLM_API_KEY` | ✅ Yes* | API key for LLM calls (Featherless or OpenRouter) | - |
| `LLM_API_BASE_URL` | No | Base URL for LLM API (auto-detected for Featherless) | `https://openrouter.ai/api/v1` |
| `LLM_MODEL_COMPLIANCE` | No | LLM model for compliance analysis | `openrouter/horizon-beta` |
| `OPENROUTER_API_KEY` | ✅ Yes* | Alternative: OpenRouter API key (backward compatible) | - |
| `OPENROUTER_MODEL_COMPLIANCE` | No | Alternative: OpenRouter model (backward compatible) | `openrouter/horizon-beta` |
| `EMBEDDING_MODEL` | ✅ Yes | Embedding model (`text-embedding-3-large` or `all-mpnet-base-v2`) | `text-embedding-3-large` |
| `OPENAI_API_KEY` | Conditional | Required if using OpenAI embeddings | - |
| `DATABASE_URL` | No | Database connection string | `sqlite:///data/app.db` |
| `DATA_ROOT` | No | Filesystem root for uploads/logs | `./data` |
| `FLASK_ENV` | No | Flask environment | `development` |

\* Either `LLM_API_KEY` or `OPENROUTER_API_KEY` is required

### Optional Configuration

- `CHUNK_SIZE`, `CHUNK_OVERLAP` - Chunking parameters
- `CONTEXT_*` - Context builder token budgets
- `REFINEMENT_*` - Retry and refinement settings

See `.env.example` for all available options.

**Verify your setup:**
```bash
python backend/scripts/check_env.py
```

## Directory Layout

```
backend/
  app/          Flask application package
  scripts/      Utility/maintenance scripts
  workers/      Future background workers live here
contracts/      JSON schemas, prompt templates, shared contracts
data/           Local storage (uploads, logs, chroma, processed)
tests/          Pytest suite (placeholder)
```

## Make Targets

| Target | Description |
| --- | --- |
| `make dev-up` | Bootstrap venv, install deps, ensure dirs, run Flask dev server. |
| `make dev-install` | Create venv (if needed) and install dependencies. |
| `make db-upgrade` | Apply the latest Alembic migrations to the configured database. |
| `make lint` | Run Ruff + Black in check mode. |
| `make test` | Run pytest with coverage reporting. |
| `make test-fast` | Run pytest without coverage (faster). |
| `make test-coverage` | Generate HTML coverage report. |
| `make type-check` | Run mypy type checking. |
| `make ensure-dirs` | Run the directory scaffolding script manually. |
| `make demo` | Run the automated demo walkthrough. |

## Pipelines

### Chunking Pipeline

Process extracted documents into semantic chunks:

```bash
python -m pipelines.chunk path/to/extracted.json --doc-id <document-id> [--replace] [--dry-run]
```

**Options:**
- `--doc-id`: Document ID (external UUID or numeric primary key)
- `--replace`: Delete existing chunks before inserting new ones
- `--dry-run`: Preview chunks without persisting to database
- `--verbose`: Print detailed chunk information

### Embedding Pipeline

Generate embeddings for document chunks and store in ChromaDB:

```bash
python -m pipelines.embed --doc-id <document-id> [--collection manual_chunks] [--batch-size 32]
```

**Options:**
- `--doc-id`: Document ID to generate embeddings for
- `--collection`: ChromaDB collection name (default: `manual_chunks`)
- `--batch-size`: Number of chunks to process per batch (default: 32)
- `--dry-run`: Show pending chunks without generating embeddings
- `--verbose`: Print detailed progress information

**Features:**
- Automatic caching of embeddings (SHA256-keyed) to avoid regeneration
- Batch processing for efficiency
- Support for OpenAI and sentence-transformers providers
- ChromaDB persistence with metadata

### Compliance Runner

Execute the sequential compliance runner against a queued audit (identified by numeric ID or external UUID):

```bash
python -m backend.app.services.run_audit --audit-id <audit-id> [--max-chunks 10]
```

The runner loads pending chunks for the audit’s document, assembles deterministic context (manual neighbors, regulation/AMC/GM snippets, evidence when enabled), and records placeholder analysis results. Real LLM integration will plug into the same interface exposed in `backend/app/services/compliance_runner.py`.
Flags and citations are synthesized automatically for each chunk (`flags` / `citations` tables) so downstream APIs can expose RED/YELLOW/GREEN findings.

### Vector Search Test

Test ChromaDB retrieval:

```bash
python scripts/vectortest.py --query "personnel qualifications" [--collection manual_chunks] [--top-k 3]
```

**Options:**
- `--query`: Query text to search for
- `--collection`: ChromaDB collection to query (default: `manual_chunks`)
- `--top-k`: Number of results to retrieve (default: 3)

### Report Generator

Render an audit's findings into Markdown (and optionally PDF via `md2pdf`):

```bash
python -m backend.app.reports.build --audit-id <audit-id> --output-dir data/reports --pdf
```

The Markdown report includes an executive summary, severity distribution, detailed findings with gaps/recommendations, and an optional appendix. PDF export requires `pip install md2pdf`.

### Developer CLI

The Developer CLI provides convenient commands for interacting with audits:

```bash
# Show audit status and progress
python cli.py status <audit-id> [--poll] [--json]

# List compliance flags
python cli.py flags <audit-id> [--severity RED] [--regulation Part-145.A.30] [--json]

# Generate audit report
python cli.py report <audit-id> [--output-dir data/reports] [--pdf] [--json]

# Compare two audits
python cli.py compare <audit-a> <audit-b> [--json]

# View compliance score history
python cli.py scores [--organization <org>] [--plot] [--json]
```

### Review UI

Access the web-based review interface for viewing audit findings:

```bash
# Start the Flask server
make dev-up

# Open in browser
http://localhost:5000/review/<audit-id>
```

The review UI provides:
- Summary statistics and compliance score
- Filterable flag listings (by severity and regulation)
- Detailed flag information with citations
- Auditor questions
- Print-friendly styling

Static HTML reports can also be generated:
```bash
python -m backend.app.reports.build --audit-id <id> --html
```

**Features:**
- **Status command**: Shows audit progress, chunk completion, and report links. Use `--poll` to continuously monitor until completion.
- **Flags command**: Lists compliance flags with filtering by severity or regulation, pagination support.
- **Report command**: Generates Markdown and optional PDF reports with download links.
- **Compare command**: Compares two audits, highlighting differences in flag counts and severity distribution.
- **Scores command**: View compliance score history with optional trend visualization.
- All commands support `--json` for machine-readable output.

### Audit Management API

Create and manage audit jobs:

```bash
# Create a new audit (full processing)
POST /audits
{
  "document_id": <document-id>,
  "is_draft": false
}

# Create a draft audit (limited processing for testing)
POST /audits
{
  "document_id": <document-id>,
  "is_draft": true
}

# Get audit details
GET /audits/<audit-id>
```

**Draft Mode:**
- Draft audits (`is_draft: true`) use lighter processing for faster test runs:
  - Limited to first 5 chunks (vs. all chunks in full mode)
  - Reduced context budgets (50% of normal)
  - No manual neighbor retrieval
  - Evidence retrieval disabled by default
  - Refinement loops skipped
- Reports clearly indicate draft status with warnings about limited processing.

## Testing

The project includes a comprehensive test suite with 79+ tests covering API endpoints, services, database models, and CLI commands.

Run tests:
```bash
make test              # With coverage
make test-fast         # Without coverage (faster)
make test-coverage     # Generate HTML report
```

See `docs/testing.md` for detailed testing documentation, including how to run test subsets, debug failures, and understand the test organization.

## CI/CD

GitHub Actions runs tests on every push and pull request:
- Python 3.11 on Ubuntu and Windows
- Coverage reporting via Codecov
- Type checking with mypy
- Linting with ruff and black

See `.github/workflows/tests.yml` for the CI configuration.

## Next Steps

- Extend the report generator with richer appendices and attachments.
- Implement LLM-backed prompt/schema validation layers for real findings.
- Add recorded fixtures and scripted demo datasets for deterministic testing.

