#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web"
STANDALONE_DIR="$WEB_DIR/.next/standalone"

if [ ! -d "$STANDALONE_DIR" ]; then
  echo "standalone output not found: $STANDALONE_DIR" >&2
  echo "Run: cd $WEB_DIR && npm run build" >&2
  exit 1
fi

rm -rf "$STANDALONE_DIR/.next/static"
cp -a "$WEB_DIR/.next/static" "$STANDALONE_DIR/.next/static"

if [ -d "$WEB_DIR/public" ]; then
  rm -rf "$STANDALONE_DIR/public"
  cp -a "$WEB_DIR/public" "$STANDALONE_DIR/public"
fi

echo "Prepared Next standalone static assets in $STANDALONE_DIR"
