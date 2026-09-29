#!/usr/bin/env bash
# Suite completa (incluye Bedrock real y Docker real) + regla de capas.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
pytest -q
echo
lint-imports
