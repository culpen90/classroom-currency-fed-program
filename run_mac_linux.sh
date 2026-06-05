#!/usr/bin/env bash
cd "$(dirname "$0")"
python3 codex_guard.py --watch --interval 5 &
CODEX_GUARD_PID=$!
trap 'kill "$CODEX_GUARD_PID" 2>/dev/null || true' EXIT
python3 classroom_currency_fed_desktop.py
