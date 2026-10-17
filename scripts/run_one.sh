#!/usr/bin/env bash
# Runs both passes for the organisation numbers in a file (default: data/input/companies.txt).
# Extra arguments go to the CLI, for example --pass1-only or --resume.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

input="${1:-data/input/companies.txt}"
shift || true
exec python -m agent_engine.cli run --input "$input" "$@"
