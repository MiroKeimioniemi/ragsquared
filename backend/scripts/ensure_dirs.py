from __future__ import annotations

import os
from pathlib import Path

DATA_ROOT = Path(os.getenv("DATA_ROOT", "./data"))
SUBDIRS = ("uploads", "processed", "logs", "chroma")


def ensure_directories() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        (DATA_ROOT / subdir).mkdir(parents=True, exist_ok=True)
    print(f"Ensured data directories under {DATA_ROOT.resolve()}")


if __name__ == "__main__":
    ensure_directories()

