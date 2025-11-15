from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REQUIRED_VARS = [
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL_COMPLIANCE",
    "EMBEDDING_MODEL",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "DATABASE_URL",
    "DATA_ROOT",
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_CANDIDATES = (
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / ".env.example",
)
SUCCESS_PREFIX = "[OK]"
ERROR_PREFIX = "[ERROR]"


def load_environment() -> None:
    for env_file in ENV_CANDIDATES:
        if env_file.exists():
            load_dotenv(env_file)
            print(f"Loaded environment file: {env_file.name}")
            return
    print("No .env file found; relying on system environment variables.")


def main() -> int:
    load_environment()
    missing = [var for var in REQUIRED_VARS if not os.getenv(var)]
    if missing:
        print(f"{ERROR_PREFIX} Missing environment variables:")
        for var in missing:
            print(f"  - {var}")
        return 1

    print(f"{SUCCESS_PREFIX} Environment looks good!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

