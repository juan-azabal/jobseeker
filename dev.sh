#!/usr/bin/env bash
# Levanta backend + frontend desde cualquier directorio.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Load local environment variables from .env if it exists
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi

# Matar lo que haya en el puerto 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

exec "$ROOT/node_modules/.bin/concurrently" \
  --names "api,web" \
  --prefix-colors "cyan,magenta" \
  --kill-others-on-fail \
  "$ROOT/venv/bin/uvicorn api.main:app --reload --port 8000" \
  "npm run dev --prefix $ROOT/web"
