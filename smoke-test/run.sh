#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE=${ENV_FILE:-"$PROJECT_ROOT/.env"}
VENV_DIR=${VENV_DIR:-"$SCRIPT_DIR/.venv"}
PYTHON_BIN=${PYTHON_BIN:-python3}

if [ ! -f "$ENV_FILE" ]; then
  printf 'Missing env file: %s\n' "$ENV_FILE" >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  printf 'Missing Python executable: %s\n' "$PYTHON_BIN" >&2
  exit 1
fi

set -a
. "$ENV_FILE"
set +a

if [ -z "${DKN_CLOUD_NA_EMAIL:-}" ] || [ -z "${DKN_CLOUD_NA_PASSWORD:-}" ]; then
  printf 'DKN_CLOUD_NA_EMAIL and DKN_CLOUD_NA_PASSWORD must be set in %s\n' "$ENV_FILE" >&2
  exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install -q -r "$SCRIPT_DIR/requirements.txt"

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$VENV_DIR/bin/python" "$SCRIPT_DIR/smoke_test.py"
