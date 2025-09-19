#!/usr/bin/env bash
set -euo pipefail

# 说明：仅启动后端FastAPI（默认端口3127）

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
BACKEND_DIR="$ROOT_DIR/backend"

echo "[dev-backend] ROOT=$ROOT_DIR"
PORT=${BACKEND_PORT:-${PORT:-3127}}

echo "[dev-backend] Creating venv and installing deps..."
python3 -m venv "$BACKEND_DIR/.venv"
source "$BACKEND_DIR/.venv/bin/activate"
pip install -U pip >/dev/null
pip install -r "$BACKEND_DIR/requirements.txt"

echo "[dev-backend] Starting uvicorn on 0.0.0.0:${PORT} ..."
cd "$BACKEND_DIR"
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}


