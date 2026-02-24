#!/bin/bash
set -e

# Ensure volume directories exist
mkdir -p /data/profiles /data/knowledge /data/seen_ids /data/cv-references

# First deploy: seed from Docker image (cp -n = no clobber)
if [ ! -f /data/.seeded ]; then
  cp -rn /app/agent/config/profiles/* /data/profiles/ 2>/dev/null || true
  cp -rn /app/agent/knowledge/* /data/knowledge/ 2>/dev/null || true
  cp -rn /app/agent/config/seen_ids/* /data/seen_ids/ 2>/dev/null || true
  touch /data/.seeded
fi

# Replace container dirs with symlinks to volume
rm -rf /app/agent/config/profiles && ln -sf /data/profiles /app/agent/config/profiles
rm -rf /app/agent/knowledge       && ln -sf /data/knowledge /app/agent/knowledge
rm -rf /app/agent/config/seen_ids && ln -sf /data/seen_ids /app/agent/config/seen_ids

# CV reference files (gitignored — must be uploaded to volume manually once)
if [ "$(ls -A /data/cv-references 2>/dev/null)" ]; then
  rm -rf /app/api/cv/references
  ln -sf /data/cv-references /app/api/cv/references
fi

exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
