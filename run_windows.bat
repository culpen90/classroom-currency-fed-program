@echo off
cd /d "%~dp0"
start "Codex Guard" /min python codex_guard.py --watch --interval 5
python classroom_currency_fed_desktop.py
pause
