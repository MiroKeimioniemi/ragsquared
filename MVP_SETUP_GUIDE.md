# MVP Setup Guide - AI Auditing System

This guide will help you get the AI Auditing System fully operational for demo/presentation.

## 🔧 Prerequisites

1. **Python 3.11+** installed
2. **Git** (if cloning)
3. **OpenRouter API Key** (for LLM calls)
4. **OpenAI API Key** (for embeddings, if using OpenAI models)

## 📋 Step-by-Step Setup

### 1. Clone/Setup Repository

```bash
cd D:\Projects\Junction25
# Or if cloning:
# git clone <repo-url>
# cd Junction25
```

### 2. Create Virtual Environment & Install Dependencies

```bash
# Create venv (if not exists)
python -m venv .venv

# Activate venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
make dev-install
# Or manually:
pip install -e .
```

### 3. Create `.env` File

Create a `.env` file in the project root with the following variables:

```bash
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=1

# Database
DATABASE_URL=sqlite:///data/app.db
DATA_ROOT=./data

# LLM API Configuration (REQUIRED for LLM compliance analysis)
# Option 1: OpenRouter
# OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# OPENROUTER_MODEL_COMPLIANCE=openrouter/horizon-beta

# Option 2: Featherless (OpenAI-compatible, supports DeepSeek and other models)
LLM_API_KEY=rc_your-featherless-api-key-here
LLM_API_BASE_URL=https://api.featherless.ai/v1
LLM_MODEL_COMPLIANCE=deepseek-ai/DeepSeek-R1-0528

# Option 3: Custom OpenAI-compatible API
# LLM_API_KEY=your-api-key
# LLM_API_BASE_URL=https://your-api.com/v1
# LLM_MODEL_COMPLIANCE=your-model-name

# Embedding Model (REQUIRED)
# Option 1: OpenAI (requires OpenAI API key)
EMBEDDING_MODEL=text-embedding-3-large
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Option 2: Sentence Transformers (free, local)
# EMBEDDING_MODEL=all-mpnet-base-v2
# (No API key needed for sentence-transformers)

# Chunking Configuration (optional, defaults shown)
CHUNK_SIZE=800
CHUNK_OVERLAP=80
CHUNK_TOKENIZER=cl100k_base
CHUNK_MAX_SECTION_TOKENS=3200

# Context Builder Configuration (optional, defaults shown)
CONTEXT_MANUAL_WINDOW=1
CONTEXT_MANUAL_TOKEN_LIMIT=1200
CONTEXT_REGULATION_TOP_K=5
CONTEXT_REGULATION_TOKEN_LIMIT=2000
CONTEXT_GUIDANCE_TOP_K=3
CONTEXT_GUIDANCE_TOKEN_LIMIT=1500
CONTEXT_EVIDENCE_TOP_K=2
CONTEXT_EVIDENCE_TOKEN_LIMIT=1000
CONTEXT_TOTAL_TOKEN_LIMIT=6000
CONTEXT_TOKENIZER=cl100k_base

# Refinement Configuration (optional, defaults shown)
REFINEMENT_MAX_ATTEMPTS=1
REFINEMENT_MANUAL_WINDOW=2
REFINEMENT_TOKEN_MULTIPLIER=1.5
REFINEMENT_INCLUDE_EVIDENCE=1

# Logging
LOG_JSON=1
```

### 4. Get API Keys

#### LLM API Key (REQUIRED)

**Option 1: Featherless API (Recommended - Free/Cheap)**
1. Go to https://featherless.ai/ (or your Featherless provider)
2. Sign up / Log in
3. Get your API key (starts with `rc_`)
4. Add to `.env`:
   ```bash
   LLM_API_KEY=rc_your-key-here
   LLM_API_BASE_URL=https://api.featherless.ai/v1
   LLM_MODEL_COMPLIANCE=deepseek-ai/DeepSeek-R1-0528
   ```

**Option 2: OpenRouter API**
1. Go to https://openrouter.ai/
2. Sign up / Log in
3. Navigate to "Keys" section
4. Create a new API key
5. Copy the key (starts with `sk-or-v1-`)
6. Add to `.env` as `OPENROUTER_API_KEY` or `LLM_API_KEY`

**Recommended Models:**
- OpenRouter: `openrouter/horizon-beta` - **Default, recommended** - Fast, cost-effective
- Featherless: `deepseek-ai/DeepSeek-R1-0528` - Fast, cost-effective
- OpenRouter: `gpt-4o-mini` - Alternative option
- OpenRouter: `gpt-4o` - More accurate, slower
- OpenRouter: `claude-3.5-sonnet` - Excellent reasoning

#### OpenAI API Key (REQUIRED if using OpenAI embeddings)
1. Go to https://platform.openai.com/api-keys
2. Sign up / Log in
3. Create a new API key
4. Copy the key (starts with `sk-`)
5. Add to `.env` as `OPENAI_API_KEY`

**Alternative:** Use sentence-transformers (free, no API key needed):
- Set `EMBEDDING_MODEL=all-mpnet-base-v2`
- No `OPENAI_API_KEY` needed

### 5. Initialize Database

```bash
# Apply database migrations
make db-upgrade

# Or manually:
alembic upgrade head
```

### 6. Verify Environment

```bash
# Check that all required environment variables are set
python backend/scripts/check_env.py
```

### 7. Start the Application

```bash
# Start Flask development server
make dev-up

# Or manually:
flask --app backend.app run --debug --host 0.0.0.0 --port 5000
```

The application will be available at:
- http://localhost:5000
- http://127.0.0.1:5000

## 🧪 Testing the Setup

### 1. Health Check
```bash
curl http://localhost:5000/healthz
# Should return: {"status": "healthy", ...}
```

### 2. Upload a Document
1. Open http://localhost:5000/documents/upload
2. Upload a test document (PDF, DOCX, etc.)
3. Select "Manual" as source type
4. The document should automatically:
   - Extract text
   - Create chunks
   - Generate embeddings
   - Run compliance audit

### 3. Check Dashboard
- Visit http://localhost:5000/dashboard
- You should see your uploaded document and audit status

### 4. View Audit Results
- Click on an audit to view findings
- Or visit: http://localhost:5000/review/<audit-id>

## 🚨 Troubleshooting

### Circular Import Error
If you see: `ImportError: cannot import name 'create_app'`
- This was fixed by importing `ComplianceRunner` directly from `compliance_runner.py`
- Restart the Flask server

### Missing API Keys
- The system will work but with limited functionality:
  - Without `OPENROUTER_API_KEY`: Uses echo/placeholder analysis (all GREEN flags)
  - Without `OPENAI_API_KEY` (if using OpenAI embeddings): Embeddings will fail
  - Use sentence-transformers as fallback: `EMBEDDING_MODEL=all-mpnet-base-v2`

### Database Errors
```bash
# Reset database (WARNING: deletes all data)
rm data/app.db
make db-upgrade
```

### Port Already in Use
```bash
# Use a different port
flask --app backend.app run --port 5001
```

## 📊 What Works Without API Keys

The system can run in **demo mode** without API keys:
- ✅ Document upload
- ✅ Text extraction
- ✅ Chunking
- ✅ Database operations
- ✅ Web UI
- ⚠️ Embeddings (needs API key or sentence-transformers)
- ⚠️ LLM Analysis (uses placeholder - all GREEN flags)

## 🎯 MVP Checklist

- [ ] Python 3.11+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`make dev-install`)
- [ ] `.env` file created with API keys
- [ ] Database initialized (`make db-upgrade`)
- [ ] Environment verified (`python backend/scripts/check_env.py`)
- [ ] Flask server running (`make dev-up`)
- [ ] Health check passes (`curl http://localhost:5000/healthz`)
- [ ] Can upload a document
- [ ] Can view dashboard
- [ ] Can view audit results

## 💰 Cost Estimates

**OpenRouter (LLM):**
- `openrouter/horizon-beta`: Check OpenRouter pricing (varies)
- `gpt-4o-mini`: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
- Typical audit: ~$0.50-$2.00 per document (depending on size)

**OpenAI Embeddings:**
- `text-embedding-3-large`: $0.13 per 1M tokens
- Typical document: ~$0.01-$0.10 per document

**Free Alternative:**
- Use `all-mpnet-base-v2` (sentence-transformers) - completely free, runs locally

## 🎬 Demo Flow

1. **Upload Regulation Document** (if not already uploaded)
   - Source type: "Regulation"
   - Organization: "EASA"
   - This provides the compliance baseline

2. **Upload Manual Document**
   - Source type: "Manual"
   - Organization: Your test organization
   - System automatically processes and audits

3. **View Results**
   - Dashboard shows audit status
   - Review page shows detailed findings
   - Reports can be generated

## 📝 Notes

- The system processes documents in the background
- Large documents may take several minutes
- Draft mode processes only first 5 chunks (faster)
- Full mode processes all chunks (slower but complete)

## 🔗 Useful Commands

```bash
# Check environment
python backend/scripts/check_env.py

# Run tests
make test

# View logs
tail -f data/logs/*.log

# Database shell
sqlite3 data/app.db

# CLI commands
python cli.py status <audit-id>
python cli.py flags <audit-id>
python cli.py report <audit-id>
```

## 🆘 Need Help?

- Check logs in `data/logs/`
- Review `docs/operations.md` for operational details
- Check `README.md` for general documentation
- Verify API keys are correct and have credits

