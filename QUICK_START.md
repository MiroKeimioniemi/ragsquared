# Quick Start Guide

Get the AI Auditing System running in 5 minutes!

## Prerequisites

- Python 3.11+
- OpenRouter API key (get free credits at https://openrouter.ai/)
- (Optional) OpenAI API key (only if using OpenAI embeddings)

## One-Command Setup

```bash
python setup.py
```

This will:
1. ✅ Check Python version
2. ✅ Create virtual environment
3. ✅ Install dependencies
4. ✅ Create `.env` file from template
5. ✅ Create data directories
6. ✅ Initialize database
7. ✅ Verify environment

## Add API Keys

Edit `.env` file and add:

```bash
# Required: LLM API key (choose one)

# Option 1: Featherless (recommended - free/cheap)
LLM_API_KEY=rc_your-featherless-key-here
LLM_API_BASE_URL=https://api.featherless.ai/v1
LLM_MODEL_COMPLIANCE=deepseek-ai/DeepSeek-R1-0528

# Option 2: OpenRouter
# OPENROUTER_API_KEY=sk-or-v1-your-key-here
# OPENROUTER_MODEL_COMPLIANCE=openrouter/horizon-beta

# Embeddings (choose one)
# Option A: OpenAI embeddings (requires API key)
EMBEDDING_MODEL=text-embedding-3-large
OPENAI_API_KEY=sk-your-key-here

# Option B: Free embeddings (no API key needed)
# EMBEDDING_MODEL=all-mpnet-base-v2
# OPENAI_API_KEY=
```

## Start the Application

```bash
make dev-up
```

Or manually:
```bash
.venv\Scripts\python.exe -m flask --app backend.app run --debug
```

## Test It

1. Visit http://localhost:5000/documents/upload
2. Upload a document (PDF, DOCX, etc.)
3. Select "Manual" as source type
4. Check http://localhost:5000/dashboard for processing status
5. View results at http://localhost:5000/review/<audit-id>

## That's It! 🎉

For detailed information, see:
- [MVP_SETUP_GUIDE.md](MVP_SETUP_GUIDE.md) - Comprehensive setup guide
- [README.md](README.md) - Full documentation

## Troubleshooting

**Port already in use?**
```bash
flask --app backend.app run --port 5001
```

**Missing API keys?**
- System will work but with placeholder analysis (all GREEN flags)
- Get OpenRouter key: https://openrouter.ai/keys
- Use free embeddings: `EMBEDDING_MODEL=all-mpnet-base-v2`

**Database errors?**
```bash
make db-upgrade
```

**Check environment:**
```bash
python backend/scripts/check_env.py
```

