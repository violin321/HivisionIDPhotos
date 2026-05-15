#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
API_SERVICE="${API_SERVICE:-idphoto-ai-api}"
WEB_SERVICE="${WEB_SERVICE:-idphoto-ai-web}"
API_LOCAL_URL="${API_LOCAL_URL:-http://127.0.0.1:18084}"
WEB_LOCAL_URL="${WEB_LOCAL_URL:-http://127.0.0.1:18083}"
EXTERNAL_URL="${EXTERNAL_URL:-https://idphoto-ai.violinai.qzz.io}"
BROWSER_UA="${BROWSER_UA:-Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-45}"
HEALTH_INTERVAL_SECONDS="${HEALTH_INTERVAL_SECONDS:-2}"

DO_RESTART=1
DO_EXTERNAL=1
STRICT_EXTERNAL=0
COMPILE_ALL_SAFE=1

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
warn() { printf '[%s] WARN: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2; }
die() { printf '[%s] ERROR: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Usage: scripts/deploy_idphoto_ai.sh [options]

Build and deploy the idphoto-ai FastAPI + Next standalone stack.

Options:
  --check, --no-restart   Run compile/build/static-copy checks, but do not restart PM2 or require live health checks.
  --skip-external         Skip external https://idphoto-ai.violinai.qzz.io checks.
  --strict-external       Treat external health/static checks as fatal. By default they are best-effort because Cloudflare may block non-browser clients.
  --deploy-api-only       Only py_compile deploy_api.py instead of all safe non-e2e scripts.
  -h, --help              Show this help.

Environment overrides:
  PYTHON_BIN, API_SERVICE, WEB_SERVICE, API_LOCAL_URL, WEB_LOCAL_URL, EXTERNAL_URL,
  HEALTH_TIMEOUT_SECONDS, HEALTH_INTERVAL_SECONDS, BROWSER_UA

Important:
  This script restarts PM2 by process name only: `pm2 restart idphoto-ai-api` and
  `pm2 restart idphoto-ai-web`. It intentionally never uses `--update-env`, so
  existing PM2 auth/session env is preserved.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check|--no-restart)
      DO_RESTART=0
      ;;
    --skip-external)
      DO_EXTERNAL=0
      ;;
    --strict-external)
      STRICT_EXTERNAL=1
      ;;
    --deploy-api-only)
      COMPILE_ALL_SAFE=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "Unknown option: $1"
      ;;
  esac
  shift
done

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

curl_status() {
  local url="$1"
  local status
  status="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 12 -A "$BROWSER_UA" "$url" || true)"
  [[ "$status" == "200" ]]
}

wait_for_url_200() {
  local name="$1"
  local url="$2"
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
  local status

  while (( SECONDS <= deadline )); do
    status="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 8 -A "$BROWSER_UA" "$url" || true)"
    if [[ "$status" == "200" ]]; then
      log "$name OK: $url"
      return 0
    fi
    sleep "$HEALTH_INTERVAL_SECONDS"
  done

  die "$name did not return HTTP 200 within ${HEALTH_TIMEOUT_SECONDS}s: $url (last status: ${status:-curl-error})"
}

find_static_chunk_path() {
  local chunk
  chunk="$(find "$WEB_DIR/.next/static/chunks" -type f -name '*.js' 2>/dev/null | sort | head -n 1 || true)"
  [[ -n "$chunk" ]] || die "No Next static chunk found under $WEB_DIR/.next/static/chunks"
  printf '%s' "/_next/static/${chunk#"$WEB_DIR/.next/static/"}"
}

compile_python() {
  [[ -x "$PYTHON_BIN" ]] || die "Python interpreter not executable: $PYTHON_BIN"
  log "Python compile: deploy_api.py"
  (cd "$ROOT_DIR" && "$PYTHON_BIN" -m py_compile deploy_api.py)

  if [[ "$COMPILE_ALL_SAFE" -eq 1 ]]; then
    log "Python compile: safe scripts/*.py (excluding e2e/test/download/build helpers)"
    mapfile -t safe_scripts < <(
      find "$ROOT_DIR/scripts" -maxdepth 1 -type f -name '*.py' \
        ! -name 'e2e_*.py' \
        ! -name 'test-*.py' \
        ! -name 'download_model.py' \
        ! -name 'build_pypi.py' \
        -print | sort
    )
    if [[ "${#safe_scripts[@]}" -gt 0 ]]; then
      (cd "$ROOT_DIR" && "$PYTHON_BIN" -m py_compile "${safe_scripts[@]}")
    else
      warn "No safe scripts/*.py found for py_compile"
    fi
  fi
}

build_web() {
  require_cmd npm
  log "Web build: npm run build"
  (cd "$WEB_DIR" && npm run build)
}

prepare_standalone_static() {
  log "Prepare Next standalone static assets"
  "$ROOT_DIR/scripts/prepare_next_standalone_static.sh"
}

restart_pm2_services_preserving_env() {
  require_cmd pm2
  log "Restart PM2 services without --update-env: $API_SERVICE"
  pm2 restart "$API_SERVICE"
  log "Restart PM2 services without --update-env: $WEB_SERVICE"
  pm2 restart "$WEB_SERVICE"
}

check_local_services() {
  local chunk_path="$1"
  wait_for_url_200 "API health" "$API_LOCAL_URL/api/health"
  wait_for_url_200 "Web home" "$WEB_LOCAL_URL/"
  wait_for_url_200 "Web static chunk" "$WEB_LOCAL_URL$chunk_path"
}

check_external_best_effort() {
  local chunk_path="$1"
  local failed=0
  log "External check with browser-like User-Agent: $EXTERNAL_URL"

  if curl_status "$EXTERNAL_URL/api/health"; then
    log "External API health OK"
  else
    warn "External API health check failed or was blocked: $EXTERNAL_URL/api/health"
    failed=1
  fi

  if curl_status "$EXTERNAL_URL$chunk_path"; then
    log "External static chunk OK"
  else
    warn "External static chunk check failed or was blocked: $EXTERNAL_URL$chunk_path"
    failed=1
  fi

  if [[ "$failed" -eq 1 && "$STRICT_EXTERNAL" -eq 1 ]]; then
    die "External checks failed in --strict-external mode"
  fi
}

main() {
  log "Deploy root: $ROOT_DIR"
  compile_python
  build_web
  prepare_standalone_static

  local chunk_path
  chunk_path="$(find_static_chunk_path)"
  log "Selected static chunk for health check: $chunk_path"

  if [[ "$DO_RESTART" -eq 1 ]]; then
    restart_pm2_services_preserving_env
    check_local_services "$chunk_path"
    if [[ "$DO_EXTERNAL" -eq 1 ]]; then
      check_external_best_effort "$chunk_path"
    fi
    log "Deploy succeeded: rebuilt web, prepared standalone static, restarted $API_SERVICE/$WEB_SERVICE, local health checks passed."
  else
    log "Check mode complete: compile/build/static-copy passed. PM2 restart and live health checks were skipped."
  fi
}

main "$@"
