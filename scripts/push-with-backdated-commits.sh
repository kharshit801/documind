#!/usr/bin/env bash
# =============================================================================
# Initialise the DocuMind repo, write 14 logical commits backdated to roughly
# 2 months ago (2026-03-08 → 2026-03-24, IST), and push to the GitHub remote.
#
# Run this from a NORMAL terminal (not the agent sandbox) so git can create
# .git/hooks/. It is idempotent-ish: if you re-run it, it will refuse to
# clobber an existing .git directory unless you pass --force-reset.
#
# Usage:
#   bash scripts/push-with-backdated-commits.sh
#   bash scripts/push-with-backdated-commits.sh --force-reset
# =============================================================================
set -euo pipefail

REMOTE_URL="https://github.com/kharshit801/documind.git"
BRANCH="main"

# Resolve the repo root regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# --- Optional reset --------------------------------------------------------
if [[ "${1:-}" == "--force-reset" ]]; then
  echo "[reset] removing existing .git/"
  rm -rf .git
fi

if [[ -d .git ]]; then
  echo "ERROR: .git already exists. Re-run with --force-reset to start over." >&2
  exit 1
fi

# --- Init repo -------------------------------------------------------------
git init -b "$BRANCH" >/dev/null
echo "[init] created repo on branch '$BRANCH'"

# --- Helpers ---------------------------------------------------------------
# Commit currently-staged changes with both author and committer dates set.
commit_at() {
  local when="$1"; shift
  local msg="$1"; shift
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" \
    git commit --quiet -m "$msg"
  printf '  [%s] %s\n' "$when" "$msg"
}

stage() {
  # Stage one or more paths; ignore missing entries gracefully.
  for p in "$@"; do
    if [[ -e "$p" ]]; then
      git add "$p"
    fi
  done
}

# All timestamps are IST (+05:30).
# Spread: 2026-03-08 → 2026-03-24 (≈ 2 months ago from 2026-05-09).

# --- 1) Project skeleton ---------------------------------------------------
stage .gitignore .env.example
commit_at "2026-03-08T11:15:00+05:30" \
  "chore: initialize project with .gitignore and env template"

# --- 2) Backend config + dep manifest --------------------------------------
stage \
  backend/app/__init__.py \
  backend/app/config.py \
  backend/.flake8 \
  backend/requirements.txt \
  backend/pytest.ini
commit_at "2026-03-08T16:42:00+05:30" \
  "feat(backend): add pydantic settings, requirements, and lint/test config"

# --- 3) File parsers -------------------------------------------------------
stage \
  backend/app/utils/__init__.py \
  backend/app/utils/parsers.py
commit_at "2026-03-09T10:23:00+05:30" \
  "feat(backend): add multi-format file parsers (PDF, DOCX, TXT, MD)"

# --- 4) Pinecone client + ingestion pipeline -------------------------------
stage \
  backend/app/services/__init__.py \
  backend/app/services/pinecone_client.py \
  backend/app/services/ingestion.py
commit_at "2026-03-10T14:55:00+05:30" \
  "feat(backend): add Pinecone client and chunk-embed-upsert ingestion pipeline"

# --- 5) Retrieval + LCEL RAG chain -----------------------------------------
stage \
  backend/app/services/retrieval.py \
  backend/app/services/llm.py
commit_at "2026-03-11T09:38:00+05:30" \
  "feat(backend): add similarity retrieval and grounded LCEL Q&A chain"

# --- 6) FastAPI routers ----------------------------------------------------
stage \
  backend/app/routers/__init__.py \
  backend/app/routers/ingest.py \
  backend/app/routers/query.py
commit_at "2026-03-12T17:12:00+05:30" \
  "feat(api): add /ingest and /query routers with full error mapping"

# --- 7) FastAPI app + Mangum Lambda handler --------------------------------
stage \
  backend/app/main.py \
  backend/lambda_handler.py
commit_at "2026-03-13T11:48:00+05:30" \
  "feat(api): wire FastAPI app, CORS, /health, and Mangum Lambda handler"

# --- 8) Backend Dockerfile -------------------------------------------------
stage backend/Dockerfile
commit_at "2026-03-14T19:24:00+05:30" \
  "build(backend): add slim Python 3.11 Dockerfile with healthcheck"

# --- 9) Backend test suite -------------------------------------------------
stage \
  backend/tests/__init__.py \
  backend/tests/conftest.py \
  backend/tests/test_ingest.py \
  backend/tests/test_query.py
commit_at "2026-03-15T13:07:00+05:30" \
  "test(backend): add pytest suite with mocked OpenAI and Pinecone"

# --- 10) Terraform infra ---------------------------------------------------
stage \
  terraform/providers.tf \
  terraform/variables.tf \
  terraform/main.tf \
  terraform/outputs.tf
commit_at "2026-03-17T15:33:00+05:30" \
  "feat(infra): add Terraform stack for Lambda, API Gateway, IAM, and S3"

# --- 11) GitHub Actions ----------------------------------------------------
stage \
  .github/workflows/ci.yml \
  .github/workflows/deploy.yml
commit_at "2026-03-19T10:18:00+05:30" \
  "ci: add GitHub Actions for lint, test, and Lambda deploy"

# --- 12) Frontend ----------------------------------------------------------
stage \
  frontend/package.json \
  frontend/package-lock.json \
  frontend/vite.config.js \
  frontend/index.html \
  frontend/Dockerfile \
  frontend/src/main.jsx \
  frontend/src/App.jsx \
  frontend/src/api.js \
  frontend/src/styles.css \
  frontend/src/components/FileUpload.jsx \
  frontend/src/components/ChatInterface.jsx
commit_at "2026-03-21T16:45:00+05:30" \
  "feat(frontend): add React + Vite SPA with file upload and chat UI"

# --- 13) docker-compose for local dev --------------------------------------
stage docker-compose.yml
commit_at "2026-03-22T12:30:00+05:30" \
  "build: add docker-compose for one-command local dev"

# --- 14) Final README ------------------------------------------------------
stage README.md
# Also stage anything else we missed (shouldn't be anything beyond this script
# itself; we explicitly leave the script untracked unless the user wants it in).
commit_at "2026-03-24T18:15:00+05:30" \
  "docs: add architecture diagram, deploy guide, and API examples"

# Optionally include this helper script in the repo as part of a final commit.
if [[ -f scripts/push-with-backdated-commits.sh ]]; then
  stage scripts/push-with-backdated-commits.sh
  if ! git diff --cached --quiet; then
    commit_at "2026-03-24T18:30:00+05:30" \
      "chore: add helper script used to bootstrap initial commit history"
  fi
fi

# --- Sanity check ----------------------------------------------------------
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "WARN: working tree still has uncommitted changes:" >&2
  git status --short >&2
fi

echo
echo "[log] commit history:"
git log --pretty=format:'  %h %ad  %s' --date=iso8601 | sed 's/^/  /'
echo

# --- Push ------------------------------------------------------------------
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE_URL"
echo "[push] origin -> $REMOTE_URL"
git push -u origin "$BRANCH"

echo
echo "Done. Visit https://github.com/kharshit801/documind to verify."
