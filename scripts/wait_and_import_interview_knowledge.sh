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
KNOWLEDGE_ROOT="${INTERVIEW_KB_CLONE_ROOT:-/app/.knowledge}"

sync_repo() {
  name="$1"
  url="$2"
  target="$KNOWLEDGE_ROOT/$name"

  if [ -d "$target/.git" ]; then
    echo "[kb-import] updating $name"
    git -C "$target" fetch --depth 1 origin
    git -C "$target" pull --ff-only
    return
  fi

  if [ -e "$target" ]; then
    echo "[kb-import] removing stale directory for $name"
    rm -rf "$target"
  fi

  echo "[kb-import] cloning $name from $url"
  git clone --depth 1 "$url" "$target"
}

mkdir -p "$KNOWLEDGE_ROOT"
sync_repo "JavaGuide" "https://github.com/Snailclimb/JavaGuide.git"
sync_repo "reactjs-interview-questions" "https://github.com/sudheerj/reactjs-interview-questions.git"
sync_repo "Waking-Up" "https://github.com/wolverinn/Waking-Up.git"

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

echo "[kb-import] API is healthy, start import."

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
