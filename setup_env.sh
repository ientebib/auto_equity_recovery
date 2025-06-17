#!/usr/bin/env bash
# Setup script for the lead_recovery project
# Creates a virtual environment and installs all dependencies.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="fresh_env"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR"/bin/activate

python -m pip install --upgrade pip

if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

if [ -f requirements-dev.txt ]; then
    pip install -r requirements-dev.txt
fi

pip install -e .

echo "Virtual environment created at '$VENV_DIR'. Activate it with 'source $VENV_DIR/bin/activate'."
