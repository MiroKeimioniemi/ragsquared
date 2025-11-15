#!/usr/bin/env python3
"""Quick setup script to initialize the AI Auditing System."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent


def print_step(step: str, message: str) -> None:
    """Print a setup step."""
    print(f"\n{'='*60}")
    print(f"Step {step}: {message}")
    print(f"{'='*60}")


def check_python_version() -> bool:
    """Check if Python version is 3.11+."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("❌ Python 3.11+ is required")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def setup_venv() -> bool:
    """Create virtual environment if it doesn't exist."""
    venv_path = PROJECT_ROOT / ".venv"
    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True
    
    print("Creating virtual environment...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to create virtual environment")
        return False


def install_dependencies() -> bool:
    """Install project dependencies."""
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if sys.platform == "win32":
        venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    
    if not venv_python.exists():
        print("❌ Virtual environment Python not found")
        return False
    
    print("Installing dependencies...")
    try:
        subprocess.run([str(venv_python), "-m", "pip", "install", "-e", "."], check=True)
        print("✅ Dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False


def setup_env_file() -> bool:
    """Create .env file from .env.example if it doesn't exist."""
    env_file = PROJECT_ROOT / ".env"
    env_example = PROJECT_ROOT / ".env.example"
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    if not env_example.exists():
        print("❌ .env.example not found")
        return False
    
    print("Creating .env file from .env.example...")
    shutil.copy(env_example, env_file)
    print("✅ .env file created")
    print("⚠️  IMPORTANT: Edit .env and add your API keys!")
    print("   - OPENROUTER_API_KEY (required)")
    print("   - OPENAI_API_KEY (required if using OpenAI embeddings)")
    return True


def setup_directories() -> bool:
    """Create required data directories."""
    dirs = [
        "data/uploads",
        "data/processed",
        "data/logs",
        "data/chroma",
        "data/cache/embeddings",
    ]
    
    for dir_path in dirs:
        full_path = PROJECT_ROOT / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
    
    print("✅ Data directories created")
    return True


def setup_database() -> bool:
    """Initialize database with migrations."""
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if sys.platform == "win32":
        venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    
    if not venv_python.exists():
        print("❌ Virtual environment Python not found")
        return False
    
    print("Running database migrations...")
    try:
        # Import here to avoid issues if dependencies aren't installed
        os.chdir(PROJECT_ROOT)
        result = subprocess.run(
            [str(venv_python), "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("✅ Database initialized")
            return True
        else:
            print(f"⚠️  Database migration output: {result.stdout}")
            print(f"⚠️  Database migration errors: {result.stderr}")
            return False
    except Exception as e:
        print(f"⚠️  Database setup warning: {e}")
        print("   You can run 'make db-upgrade' manually later")
        return True  # Not critical


def verify_environment() -> bool:
    """Verify environment variables are set."""
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if sys.platform == "win32":
        venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    
    if not venv_python.exists():
        return False
    
    print("Verifying environment...")
    try:
        result = subprocess.run(
            [str(venv_python), "backend/scripts/check_env.py"],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode == 0:
            print("✅ Environment verified")
            return True
        else:
            print("⚠️  Some environment variables may be missing")
            print("   Edit .env file and add your API keys")
            return True  # Not blocking
    except Exception as e:
        print(f"⚠️  Could not verify environment: {e}")
        return True  # Not blocking


def main() -> int:
    """Run the setup process."""
    print("\n" + "="*60)
    print("AI Auditing System - Setup Script")
    print("="*60)
    
    steps = [
        ("1", "Checking Python version", check_python_version),
        ("2", "Setting up virtual environment", setup_venv),
        ("3", "Installing dependencies", install_dependencies),
        ("4", "Creating .env file", setup_env_file),
        ("5", "Creating data directories", setup_directories),
        ("6", "Initializing database", setup_database),
        ("7", "Verifying environment", verify_environment),
    ]
    
    for step_num, step_name, step_func in steps:
        print_step(step_num, step_name)
        if not step_func():
            print(f"\n❌ Setup failed at step {step_num}")
            return 1
    
    print("\n" + "="*60)
    print("✅ Setup Complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Edit .env file and add your API keys:")
    print("   - OPENROUTER_API_KEY (get from https://openrouter.ai/keys)")
    print("   - OPENAI_API_KEY (if using OpenAI embeddings)")
    print("   - Or use sentence-transformers (free): set EMBEDDING_MODEL=all-mpnet-base-v2")
    print("\n2. Start the application:")
    print("   make dev-up")
    print("   # Or manually:")
    print("   .venv\\Scripts\\python.exe -m flask --app backend.app run --debug")
    print("\n3. Visit http://localhost:5000")
    print("\nFor detailed setup instructions, see MVP_SETUP_GUIDE.md")
    print("="*60 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

