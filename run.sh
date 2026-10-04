#!/usr/bin/env sh
# world.execute(me); TUI MV - one-click build for macOS / Linux
# Usage: ./run.sh  (or: sh run.sh)
set -e
cd "$(dirname "$0")"

PYEXE=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then
    PYEXE="$c"
    break
  fi
done

if [ -z "$PYEXE" ]; then
  echo
  echo "  [X] Python not found."
  echo
  echo "      Install Python 3.9 or newer first."
  echo
  exit 1
fi

echo
echo "  Starting one-click build."
echo "  First run creates .venv and downloads dependencies."
echo

exec "$PYEXE" ./oneclick.py "$@"
