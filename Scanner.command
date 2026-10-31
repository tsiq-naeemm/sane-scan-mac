#!/bin/bash
# Double-click this file in Finder to open the scanner GUI.
# (First time: right-click → Open, to get past Gatekeeper.)

# Pick a python3 that has Tkinter (Homebrew's, installed by installer.sh).
PY=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -x "$cand" ]; then PY="$cand"; break; fi
done

if [ -z "$PY" ]; then
  echo "python3 not found. Run installer.sh first."
  read -r -p "Press Return to close."
  exit 1
fi

DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$PY" "$DIR/scanner_gui.py"
