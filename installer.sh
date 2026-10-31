#!/bin/bash
#
# installer.sh — Set up everything needed to drive a Canon LiDE 110
# (and most other SANE-supported scanners) on macOS, including the GUI.
#
# Installs:  Homebrew (if missing) -> sane-backends -> python-tk
# Verifies:  the scanner is detected by SANE
#
# Usage:  ./installer.sh
#
set -euo pipefail

# ---- pretty output helpers -------------------------------------------------
bold() { printf "\033[1m%s\033[0m\n" "$1"; }
ok()   { printf "\033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "\033[33m!\033[0m %s\n" "$1"; }
err()  { printf "\033[31m✗\033[0m %s\n" "$1"; }

bold "Canon LiDE 110 scanner — setup"
echo

# ---- 1. Homebrew -----------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
  warn "Homebrew is not installed."
  read -r -p "Install Homebrew now? (needs your password & network) [y/N] " reply
  if [[ "$reply" =~ ^[Yy]$ ]]; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  else
    err "Homebrew is required. Aborting."
    exit 1
  fi
fi

# Make sure brew is on PATH for the rest of this script (Apple Silicon default).
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi
ok "Homebrew found: $(brew --prefix)"

# ---- 2. SANE backends (the actual scanner driver) --------------------------
if brew list sane-backends >/dev/null 2>&1; then
  ok "sane-backends already installed"
else
  bold "Installing sane-backends (this is the scanner driver)…"
  brew install sane-backends
  ok "sane-backends installed"
fi

# ---- 3. Tkinter for the GUI ------------------------------------------------
if brew list python-tk >/dev/null 2>&1; then
  ok "python-tk already installed"
else
  bold "Installing python-tk (needed for the GUI)…"
  brew install python-tk
  ok "python-tk installed"
fi

# ---- 4. Verify the scanner -------------------------------------------------
echo
bold "Looking for your scanner…"
if scanimage -L 2>/dev/null | grep -qi "genesys\|canon\|lide"; then
  ok "Scanner detected:"
  scanimage -L 2>/dev/null | sed 's/^/    /'
  echo
  ok "All set. Launch the GUI by double-clicking 'Scanner.command'."
else
  warn "No scanner detected right now."
  echo "    • Make sure the scanner is plugged in and powered on."
  echo "    • Then re-run:  scanimage -L"
  echo "    The driver is installed either way — you can launch the GUI once"
  echo "    the scanner shows up."
fi
