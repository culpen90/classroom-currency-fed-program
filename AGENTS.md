# Codex Guidance

## Project

This repository contains a small classroom central-bank app:

- `classroom_currency_fed_desktop.py`: Python/tkinter desktop app.
- `classroom_currency_fed_browser.html`: single-file browser app.
- `codex_guard.py`: local guard that runs checks and calls the Codex CLI.

## Constraints

- Keep the desktop app on the Python standard library unless the user explicitly asks for dependencies.
- Keep the browser app as a standalone offline HTML file.
- Do not add OpenAI API-key handling, OpenAI SDK calls, or stored secrets to this app.
- Codex integration must use the local Codex CLI and the user's own `codex login` session.
- Do not edit `classroom_central_bank_data.json`, backups, exports, or generated reports unless the user explicitly asks.

## Checks

Run these before finishing code changes:

```bash
python3 -m py_compile classroom_currency_fed_desktop.py
python3 codex_guard.py --once --local-only
```

If `python3` is not available on Windows, use `python` instead.
