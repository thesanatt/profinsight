#!/usr/bin/env bash
# ProfInsight deployment helper.
#
# Usage:
#   ./deploy.sh setup         # one-time: install backend + frontend deps
#   ./deploy.sh analyze       # (re)run the Bayesian pipeline on every data/<school>.json
#   ./deploy.sh build         # build the frontend for production
#   ./deploy.sh dev           # run API + frontend locally (foreground, two processes)
#   ./deploy.sh serve         # serve API + built frontend on :8000 (prod-like)
#   ./deploy.sh deploy        # full: setup → analyze → build → serve
#   ./deploy.sh scrape <slug> <"School Name">   # scrape a new school, then analyze
#   ./deploy.sh refresh       # refresh every already-scraped school
#   ./deploy.sh status        # quick sanity check
#   ./deploy.sh help          # print this
#
# Env overrides:
#   PORT=8000            API port
#   FRONTEND_PORT=5173   dev server port
#   PYTHON=python3       interpreter
#   MAX_PROFESSORS=500   per-school scraping cap
#
# The script is idempotent. Re-running any step is safe.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
PORT="${PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
MAX_PROFESSORS="${MAX_PROFESSORS:-500}"
VENV="$ROOT/venv"

# ---------- helpers ----------
c_reset=$'\033[0m'; c_green=$'\033[32m'; c_yellow=$'\033[33m'; c_red=$'\033[31m'; c_bold=$'\033[1m'
log()  { printf '%s[deploy]%s %s\n' "$c_green" "$c_reset" "$*"; }
warn() { printf '%s[deploy]%s %s\n' "$c_yellow" "$c_reset" "$*"; }
err()  { printf '%s[deploy]%s %s\n' "$c_red"    "$c_reset" "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }

activate_venv() {
  if [[ ! -d "$VENV" ]]; then
    err "venv missing. Run './deploy.sh setup' first."
    exit 1
  fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
}

# ---------- commands ----------
cmd_setup() {
  log "Checking prerequisites..."
  have "$PYTHON" || { err "$PYTHON not found"; exit 1; }
  have node      || { err "node not found (need Node.js 18+)"; exit 1; }
  have npm       || { err "npm not found"; exit 1; }

  if [[ ! -d "$VENV" ]]; then
    log "Creating Python venv at $VENV"
    "$PYTHON" -m venv "$VENV"
  fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"

  log "Installing Python dependencies"
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt

  log "Installing frontend dependencies"
  (cd frontend && npm install --silent)

  log "Setup complete."
}

cmd_analyze() {
  activate_venv
  shopt -s nullglob
  local raw analyzed slug count=0
  for raw in data/*.json; do
    # skip already-analyzed files
    [[ "$raw" == *_analyzed.json ]] && continue
    slug="$(basename "$raw" .json)"
    analyzed="data/${slug}_analyzed.json"
    log "Analyzing $slug"
    "$PYTHON" bayesian_pipeline.py --input "$raw" --output "$analyzed"
    count=$((count + 1))
  done
  shopt -u nullglob
  log "Analyzed $count school file(s)."
}

cmd_build() {
  log "Building frontend (vite)"
  (cd frontend && npm run build --silent)
  log "Frontend built to frontend/dist/"
}

cmd_dev() {
  activate_venv
  log "Starting API on :$PORT and frontend dev server on :$FRONTEND_PORT"
  log "Ctrl-C stops both."
  # Launch both; trap cleans them up together.
  uvicorn api:app --reload --port "$PORT" --host 0.0.0.0 &
  api_pid=$!
  (cd frontend && npm run dev -- --port "$FRONTEND_PORT") &
  fe_pid=$!
  trap 'log "stopping..."; kill "$api_pid" "$fe_pid" 2>/dev/null || true; wait 2>/dev/null || true' INT TERM
  wait "$api_pid" "$fe_pid"
}

cmd_serve() {
  activate_venv
  if [[ ! -d frontend/dist ]]; then
    warn "frontend/dist missing — running build first"
    cmd_build
  fi
  log "Serving API on :$PORT (API + built frontend if api.py mounts it)"
  exec uvicorn api:app --host 0.0.0.0 --port "$PORT"
}

cmd_scrape() {
  activate_venv
  local slug="${1:-}" name="${2:-}"
  [[ -z "$slug" || -z "$name" ]] && { err "usage: deploy.sh scrape <slug> \"<School Name>\""; exit 1; }
  local raw="data/${slug}.json" analyzed="data/${slug}_analyzed.json"
  log "Scraping $name -> $raw (max $MAX_PROFESSORS professors)"
  "$PYTHON" rmp_scraper.py --school "$name" --max-professors "$MAX_PROFESSORS" --output "$raw"
  log "Analyzing -> $analyzed"
  "$PYTHON" bayesian_pipeline.py --input "$raw" --output "$analyzed"
  log "Done. Restart the API so it picks up the new school."
}

cmd_refresh() {
  activate_venv
  log "Refreshing every already-scraped school"
  "$PYTHON" bulk_update.py --refresh --max-professors "$MAX_PROFESSORS"
}

cmd_status() {
  log "Project root: $ROOT"
  log "Python:       $($PYTHON --version 2>&1 || echo missing)"
  log "Node:         $(node --version 2>&1 || echo missing)"
  log "venv:         $([[ -d $VENV ]] && echo present || echo missing)"
  log "frontend/dist: $([[ -d frontend/dist ]] && echo present || echo missing)"
  log "Analyzed schools: $(ls data/*_analyzed.json 2>/dev/null | wc -l | tr -d ' ')"
  log "Raw schools:      $(ls data/*.json 2>/dev/null | grep -v _analyzed | wc -l | tr -d ' ')"
}

cmd_deploy() {
  cmd_setup
  cmd_analyze
  cmd_build
  log "Everything built. Run './deploy.sh serve' to start, or deploy to your host."
  log "Production: frontend/dist -> Vercel; API (this repo) -> Render with start cmd:"
  log "  uvicorn api:app --host 0.0.0.0 --port \$PORT"
}

cmd_help() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
}

main() {
  local sub="${1:-help}"; shift || true
  case "$sub" in
    setup)    cmd_setup "$@";;
    analyze)  cmd_analyze "$@";;
    build)    cmd_build "$@";;
    dev)      cmd_dev "$@";;
    serve)    cmd_serve "$@";;
    scrape)   cmd_scrape "$@";;
    refresh)  cmd_refresh "$@";;
    status)   cmd_status "$@";;
    deploy)   cmd_deploy "$@";;
    help|-h|--help) cmd_help;;
    *) err "unknown command: $sub"; cmd_help; exit 1;;
  esac
}

main "$@"
