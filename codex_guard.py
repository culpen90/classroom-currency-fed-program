#!/usr/bin/env python3
"""Local Codex guard for the Classroom Currency Fed program.

The guard keeps OpenAI credentials out of this project. It calls the Codex CLI,
which reuses the user's own Codex/ChatGPT login.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parent
DESKTOP_APP = ROOT / "classroom_currency_fed_desktop.py"
BROWSER_APP = ROOT / "classroom_currency_fed_browser.html"
DATA_FILE = ROOT / "classroom_central_bank_data.json"
LAST_REPORT = ROOT / "codex_guard_last_run.txt"
WATCHED_FILES = [
    DESKTOP_APP,
    BROWSER_APP,
    ROOT / "README.md",
    ROOT / "README.txt",
    ROOT / "run_mac_linux.sh",
    ROOT / "run_windows.bat",
]


@dataclass
class CheckResult:
    name: str
    ok: bool
    output: str
    skipped: bool = False

    @property
    def status(self) -> str:
        if self.skipped:
            return "SKIP"
        return "OK" if self.ok else "FAIL"


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_command(command: Sequence[str], timeout: int = 120, input_text: Optional[str] = None) -> Tuple[int, str]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return 127, str(exc)
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return 124, f"Timed out after {timeout} seconds.\n{output}".strip()

    output = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, output.strip()


def shell_lookup(command: str) -> Optional[str]:
    """Find commands from the user's interactive shell when this PATH is sparse."""
    if os.name == "nt":
        return None
    shell = os.environ.get("SHELL") or "bash"
    if "/" in shell and not Path(shell).exists():
        shell = "bash"
    code, output = run_command([shell, "-ic", f"command -v {command}"], timeout=15)
    if code != 0:
        return None
    for line in output.splitlines():
        candidate = line.strip()
        if candidate.startswith("/") and Path(candidate).exists():
            return candidate
    return None


def find_command(command: str) -> Optional[str]:
    direct = shutil.which(command)
    if direct:
        return direct

    from_shell = shell_lookup(command)
    if from_shell:
        return from_shell

    home = Path.home()
    candidates: List[str] = [
        str(home / ".local" / "bin" / command),
        str(home / ".npm-global" / "bin" / command),
    ]
    if os.name != "nt":
        candidates.extend(
            glob.glob(str(home / ".config" / "nvm" / "versions" / "node" / "*" / "bin" / command))
        )
        candidates.extend(glob.glob(str(home / ".nvm" / "versions" / "node" / "*" / "bin" / command)))
    else:
        candidates.extend(
            [
                str(home / "AppData" / "Roaming" / "npm" / f"{command}.cmd"),
                str(home / "AppData" / "Roaming" / "npm" / command),
            ]
        )

    existing = [Path(path) for path in candidates if Path(path).exists()]
    if not existing:
        return None
    newest = max(existing, key=lambda path: path.stat().st_mtime)
    return str(newest)


def check_python_syntax() -> CheckResult:
    code, output = run_command([sys.executable, "-m", "py_compile", str(DESKTOP_APP)])
    return CheckResult("Python syntax", code == 0, output or "Desktop app compiles.")


def extract_browser_script() -> str:
    html = BROWSER_APP.read_text(encoding="utf-8")
    blocks = re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.IGNORECASE | re.DOTALL)
    return "\n\n".join(blocks)


def check_browser_javascript() -> CheckResult:
    node = find_command("node")
    if not node:
        return CheckResult(
            "Browser JavaScript syntax",
            True,
            "Node.js was not found, so browser JavaScript syntax was not checked.",
            skipped=True,
        )

    script = extract_browser_script()
    checker = "const fs = require('fs'); new Function(fs.readFileSync(0, 'utf8'));"
    code, output = run_command([node, "-e", checker], input_text=script)
    return CheckResult("Browser JavaScript syntax", code == 0, output or "Browser script parses.")


def check_data_file() -> CheckResult:
    if not DATA_FILE.exists():
        return CheckResult("Local data file", True, "No local data file exists yet.", skipped=True)
    try:
        with DATA_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return CheckResult("Local data file", False, f"Data file is not valid JSON: {exc}")

    required = ["settings", "accounts", "transactions", "loans", "price_index"]
    missing = [key for key in required if key not in data]
    if missing:
        return CheckResult("Local data file", False, f"Data file is missing keys: {', '.join(missing)}")
    if not isinstance(data.get("accounts"), list):
        return CheckResult("Local data file", False, "Data file accounts value must be a list.")
    return CheckResult("Local data file", True, "Local data file shape looks valid.")


def run_local_checks() -> List[CheckResult]:
    return [
        check_python_syntax(),
        check_browser_javascript(),
        check_data_file(),
    ]


def format_results(results: Iterable[CheckResult]) -> str:
    lines: List[str] = []
    for result in results:
        lines.append(f"[{result.status}] {result.name}")
        if result.output:
            lines.append(textwrap.indent(result.output, "  "))
    return "\n".join(lines)


def codex_prompt(results: List[CheckResult], allow_edits: bool, codex_review: bool) -> str:
    local_output = format_results(results)
    mode = "fix the mistake with the smallest safe code change" if allow_edits else "review and report only"
    review_line = (
        "Also inspect the app for likely user-facing mistakes even if the local checks pass."
        if codex_review
        else "Focus on the local check failure first."
    )
    return textwrap.dedent(
        f"""
        You are the OpenAI Codex guard for the Classroom Currency Fed repository.

        Goal: {mode}. {review_line}

        Local check output:
        {local_output}

        Required context:
        - Desktop app: classroom_currency_fed_desktop.py
        - Browser app: classroom_currency_fed_browser.html
        - Guard script: codex_guard.py
        - This project must not collect OpenAI API keys or add OpenAI SDK/API-key auth.
        - Use the existing Codex CLI authentication model: users run `codex login` and sign in with ChatGPT/OpenAI.
        - Preserve classroom data. Do not edit classroom_central_bank_data.json, backups, exports, or generated reports unless a user explicitly asks.
        - Keep dependencies minimal. The app currently uses the Python standard library and browser-native JavaScript.

        Verification to run before finishing:
        - `{sys.executable} -m py_compile classroom_currency_fed_desktop.py`
        - `{sys.executable} codex_guard.py --once --local-only`

        Finish with a concise summary of what you changed or, in report-only mode, the issues you found.
        """
    ).strip()


def run_codex(results: List[CheckResult], allow_edits: bool, codex_review: bool) -> int:
    codex = find_command("codex")
    if not codex:
        message = textwrap.dedent(
            """
            Codex CLI was not found from this process.

            Install Codex, then run:
              codex login

            Choose ChatGPT/OpenAI sign-in. This project does not need an OpenAI API key.
            """
        ).strip()
        LAST_REPORT.write_text(message + "\n", encoding="utf-8")
        print(message)
        return 127

    prompt = codex_prompt(results, allow_edits=allow_edits, codex_review=codex_review)
    sandbox = "workspace-write" if allow_edits else "read-only"
    command = [
        codex,
        "exec",
        "-C",
        str(ROOT),
        "-m",
        "gpt-5.5",
        "-c",
        'model_reasoning_effort="xhigh"',
        "-c",
        'approval_policy="never"',
        "-s",
        sandbox,
        prompt,
    ]

    print(f"[{timestamp()}] Running Codex guard with gpt-5.5 / xhigh / {sandbox}.")
    code, output = run_command(command, timeout=1800)
    LAST_REPORT.write_text(output + "\n", encoding="utf-8")
    if output:
        print(output)
    if code != 0:
        print(
            "\nCodex did not complete successfully. If this is an auth problem, run `codex login` "
            "and choose ChatGPT/OpenAI sign-in; no API key is needed for this project."
        )
    return code


def watched_snapshot() -> Tuple[Tuple[str, int, int], ...]:
    rows: List[Tuple[str, int, int]] = []
    for path in WATCHED_FILES:
        if path.exists():
            stat = path.stat()
            rows.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(rows)


def check_and_maybe_call_codex(args: argparse.Namespace) -> int:
    results = run_local_checks()
    failures = [result for result in results if not result.ok and not result.skipped]
    print(f"[{timestamp()}] Local guard checks")
    print(format_results(results))

    if args.local_only:
        return 1 if failures else 0

    should_run_codex = bool(failures) or args.codex_review
    if not should_run_codex:
        return 0

    allow_edits = (bool(failures) and not args.no_fix) or args.auto_fix
    codex_code = run_codex(results, allow_edits=allow_edits, codex_review=args.codex_review)
    if codex_code != 0:
        return codex_code

    if allow_edits:
        print(f"[{timestamp()}] Rechecking after Codex.")
        after = run_local_checks()
        print(format_results(after))
        return 1 if any(not result.ok and not result.skipped for result in after) else 0
    return 0 if not failures else 1


def watch(args: argparse.Namespace) -> int:
    print(f"[{timestamp()}] Codex guard is watching this project. Press Ctrl+C to stop.")
    previous: Optional[Tuple[Tuple[str, int, int], ...]] = None
    exit_code = 0
    try:
        while True:
            current = watched_snapshot()
            if current != previous:
                previous = current
                exit_code = check_and_maybe_call_codex(args)
            time.sleep(max(args.interval, 1.0))
    except KeyboardInterrupt:
        print(f"\n[{timestamp()}] Codex guard stopped.")
    return exit_code


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local checks and call OpenAI Codex when mistakes appear.")
    parser.add_argument("--once", action="store_true", help="Run one guard pass. This is the default unless --watch is used.")
    parser.add_argument("--watch", action="store_true", help="Keep watching project files and rerun the guard when they change.")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between watch checks.")
    parser.add_argument("--local-only", action="store_true", help="Run local checks without invoking Codex.")
    parser.add_argument("--codex-review", action="store_true", help="Ask Codex to inspect the app even when local checks pass.")
    parser.add_argument("--auto-fix", action="store_true", help="Allow Codex to edit during optional review runs.")
    parser.add_argument("--no-fix", action="store_true", help="Never allow Codex to edit; report only.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.no_fix and args.auto_fix:
        print("--no-fix and --auto-fix cannot be used together.")
        return 2
    if args.watch:
        return watch(args)
    return check_and_maybe_call_codex(args)


if __name__ == "__main__":
    raise SystemExit(main())
