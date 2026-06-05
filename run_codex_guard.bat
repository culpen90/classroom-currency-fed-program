@echo off
cd /d "%~dp0"
python codex_guard.py --watch --interval 5
pause
