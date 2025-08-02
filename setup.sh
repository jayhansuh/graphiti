#!/usr/bin/env bash
set -e

# Setup development environment using uv
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

uv sync --extra dev
uv run pre-commit install
