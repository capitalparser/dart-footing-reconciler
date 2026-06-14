#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYODIDE_DIR="$ROOT_DIR/vendor/pyodide"
PYODIDE_JS="$PYODIDE_DIR/pyodide.js"
TARBALL="/tmp/pyodide-0.26.4.tar.bz2"
URL="https://github.com/pyodide/pyodide/releases/download/0.26.4/pyodide-0.26.4.tar.bz2"

if [[ -f "$PYODIDE_JS" ]]; then
  echo "PyOdide 0.26.4 already present at $PYODIDE_JS; skipping download."
  exit 0
fi

mkdir -p "$PYODIDE_DIR"
curl -L -o "$TARBALL" "$URL"
tar -xjf "$TARBALL" -C "$PYODIDE_DIR" --strip-components=1
echo "PyOdide 0.26.4 extracted to $PYODIDE_DIR"
