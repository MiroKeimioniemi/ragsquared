# Featherless API Setup Guide

This guide shows you how to configure the AI Auditing System to use Featherless API (OpenAI-compatible) instead of OpenRouter.

## What is Featherless?

Featherless is an OpenAI-compatible API that provides access to open-source LLMs like DeepSeek-R1. It's often cheaper or free compared to OpenRouter.

## Quick Setup

### 1. Get Your Featherless API Key

1. Go to your Featherless provider (e.g., https://featherless.ai/)
2. Sign up / Log in
3. Get your API key (starts with `rc_`)

### 2. Update `.env` File

Add these lines to your `.env` file:

```bash
# Featherless API Configuration
LLM_API_KEY=rc_your-featherless-api-key-here
LLM_API_BASE_URL=https://api.featherless.ai/v1
LLM_MODEL_COMPLIANCE=deepseek-ai/DeepSeek-R1-0528
```

**That's it!** The system will automatically detect Featherless keys (they start with `rc_`) and use the correct base URL.

## Example Configuration

```bash
# .env file
LLM_API_KEY=rc_b36902e128e9e569d9e66576a546ac78d8ed5747071825ff6ccf9f4fd0ded43f
LLM_API_BASE_URL=https://api.featherless.ai/v1
LLM_MODEL_COMPLIANCE=deepseek-ai/DeepSeek-R1-0528

# Embeddings (still needed)
EMBEDDING_MODEL=all-mpnet-base-v2  # Free option
# OR
EMBEDDING_MODEL=text-embedding-3-large
OPENAI_API_KEY=sk-your-openai-key
```

## How It Works

The system automatically detects Featherless API keys by checking if they start with `rc_`. When detected:

1. ✅ Base URL is automatically set to `https://api.featherless.ai/v1`
2. ✅ Uses OpenAI-compatible API format
3. ✅ Works with all OpenAI-compatible models

## Supported Models

Check your Featherless provider for available models. Common examples:
- `deepseek-ai/DeepSeek-R1-0528` - Recommended
- Other DeepSeek variants
- Any OpenAI-compatible model your provider supports

## Testing

After updating `.env`, restart the Flask server:

```bash
# Stop current server (Ctrl+C)
# Then restart:
make dev-up
```

Upload a document and check the logs - you should see:
```
Detected Featherless API key, using Featherless base URL
Calling LLM API: https://api.featherless.ai/v1/chat/completions with model: deepseek-ai/DeepSeek-R1-0528
```

## Troubleshooting

**API key not working?**
- Verify the key starts with `rc_`
- Check that the key is valid in your Featherless dashboard
- Ensure `LLM_API_BASE_URL` is set correctly

**Model not found?**
- Check available models in your Featherless provider dashboard
- Update `LLM_MODEL_COMPLIANCE` with the correct model name

**Still using OpenRouter?**
- Make sure `LLM_API_KEY` is set (not just `OPENROUTER_API_KEY`)
- The system prioritizes `LLM_API_KEY` over `OPENROUTER_API_KEY`

## Backward Compatibility

The system still supports OpenRouter:
- If you use `OPENROUTER_API_KEY`, it will work as before
- Or use `LLM_API_KEY` with OpenRouter key and set `LLM_API_BASE_URL=https://openrouter.ai/api/v1`

## Cost Comparison

- **Featherless**: Often free or very cheap (check your provider)
- **OpenRouter**: Pay-per-use, varies by model
- **OpenAI Direct**: Most expensive

For hackathons/demos, Featherless is often the best choice!

