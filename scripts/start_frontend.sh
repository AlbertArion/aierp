#!/usr/bin/env bash
set -euo pipefail

# 说明：仅启动前端Vite（默认端口5173）

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "[dev-frontend] ROOT=$ROOT_DIR"
cd "$FRONTEND_DIR"

echo "[dev-frontend] Using npm as package manager"
npm i

echo "[dev-frontend] Starting dev server on 0.0.0.0:5173 ..."
exec npm run dev -- --host 0.0.0.0 --port 5173


