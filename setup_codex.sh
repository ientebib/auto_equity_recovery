#!/usr/bin/env bash
# Quick setup script for Codex environments
# Creates a virtual environment and installs project dependencies.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d "fresh_env" ]; then
    python3 -m venv fresh_env
fi

source fresh_env/bin/activate

python -m pip install --upgrade pip

if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

if [ -f requirements-dev.txt ]; then
    pip install -r requirements-dev.txt
fi

pip install -e .

echo "Environment setup complete. Activate it with 'source fresh_env/bin/activate'."
