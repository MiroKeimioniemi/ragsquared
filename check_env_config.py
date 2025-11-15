#!/usr/bin/env python3
"""Check current environment configuration for embedding model."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load .env file if it exists
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"[OK] Loaded .env file: {env_file}")
else:
    print("[WARN] No .env file found, using system environment variables")
    load_dotenv()  # Still try to load from system

# Check embedding model
embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
embedding_api_base_url = os.getenv("EMBEDDING_API_BASE_URL") or os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1")
print(f"\n=== EMBEDDING CONFIGURATION ===")
print(f"EMBEDDING_MODEL: {embedding_model}")
print(f"EMBEDDING_API_BASE_URL: {embedding_api_base_url}")

# Model dimensions mapping (OpenRouter-supported models)
MODEL_DIMENSIONS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
    # Add other OpenRouter-supported embedding models here
}

expected_dims = MODEL_DIMENSIONS.get(embedding_model, "UNKNOWN")
print(f"Expected dimensions: {expected_dims}")

# Check API keys
openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
llm_key = os.getenv("LLM_API_KEY", "")

print(f"\n=== API KEYS ===")
print(f"OPENROUTER_API_KEY: {'SET' if openrouter_key else 'NOT SET'}")
print(f"LLM_API_KEY: {'SET' if llm_key else 'NOT SET'}")

# Provider is always OpenRouter now
provider = "OpenRouter"
if not openrouter_key and not llm_key:
    print(f"\n[ERROR] {provider} requires an API key but none found!")
    print(f"   Please set OPENROUTER_API_KEY or LLM_API_KEY in your .env file")
else:
    print(f"\nProvider: {provider} (using OpenRouter API)")

print(f"\n=== SUMMARY ===")
if expected_dims == "UNKNOWN":
    print(f"[WARN] Unknown embedding model: {embedding_model}")
    print(f"   Make sure this model is supported by OpenRouter")
    print(f"   Common models: text-embedding-3-large (3072 dims), text-embedding-3-small (1536 dims)")
else:
    print(f"Embedding model: {embedding_model} ({expected_dims} dimensions)")
    print(f"[OK] Using OpenRouter for embedding generation")

