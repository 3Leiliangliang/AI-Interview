#!/bin/sh

set -eu

IMPORT_ENABLED="${AUTO_IMPORT_INTERVIEW_KB:-false}"
if [ "$IMPORT_ENABLED" != "true" ]; then
  echo "[kb-import] AUTO_IMPORT_INTERVIEW_KB is not true, skip."
  exit 0
fi

BASE_URL="${INTERVIEW_KB_IMPORT_BASE_URL:-http://api:5050/api}"
SENTINEL="${INTERVIEW_KB_IMPORT_SENTINEL:-/app/saves/.interview_knowledge_imported}"
FORCE_IMPORT="${AUTO_IMPORT_INTERVIEW_KB_FORCE:-false}"
FORCE_REINDEX="${AUTO_IMPORT_INTERVIEW_KB_FORCE_REINDEX:-false}"
BATCH_SIZE="${INTERVIEW_KB_IMPORT_BATCH_SIZE:-20}"
USERNAME="${AI_INTERVIEW_SUPER_ADMIN_NAME:-admin}"
PASSWORD="${AI_INTERVIEW_SUPER_ADMIN_PASSWORD:-admin123}"

if [ -f "$SENTINEL" ] && [ "$FORCE_IMPORT" != "true" ]; then
  echo "[kb-import] sentinel exists: $SENTINEL, skip."
  exit 0
fi

echo "[kb-import] waiting for API health: $BASE_URL/system/health"
attempt=0
until curl -fsS "$BASE_URL/system/health" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 120 ]; then
    echo "[kb-import] API health check timed out."
    exit 1
  fi
  sleep 2
done

echo "[kb-import] API is healthy, start syncing curated interview sources and import."

FORCE_REINDEX_ARG=""
if [ "$FORCE_REINDEX" = "true" ]; then
  FORCE_REINDEX_ARG="--force-reindex"
fi

uv run --no-dev python /app/scripts/import_interview_knowledge.py \
  --base-url "$BASE_URL" \
  --username "$USERNAME" \
  --password "$PASSWORD" \
  --batch-size "$BATCH_SIZE" \
  $FORCE_REINDEX_ARG

mkdir -p "$(dirname "$SENTINEL")"
touch "$SENTINEL"
echo "[kb-import] import finished, sentinel written to $SENTINEL"
