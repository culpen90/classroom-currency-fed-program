#!/usr/bin/env python3
"""Codex economy checker for the Classroom Currency Fed program.

This script does not collect OpenAI API keys. It calls the local Codex CLI,
which reuses the user's own `codex login` ChatGPT/OpenAI session.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "classroom_central_bank_data.json"
LAST_REPORT = ROOT / "codex_guard_last_run.txt"
LAST_STARTUP_REPORT = ROOT / "codex_start_currency_last_run.txt"
STARTUP_CHAT_TRANSCRIPT = ROOT / "codex_start_currency_chat.json"


@dataclass
class CheckResult:
    level: str
    check: str
    details: str


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
        candidates.extend(glob.glob(str(home / ".config" / "nvm" / "versions" / "node" / "*" / "bin" / command)))
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


def as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def load_data(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, f"No classroom data file exists yet at {path}."
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return None, f"Could not read classroom data: {exc}"
    if not isinstance(data, dict):
        return None, "Classroom data must be a JSON object."
    return data, None


def data_format(data: Dict[str, Any]) -> str:
    if "price_index" in data:
        return "desktop"
    if "prices" in data:
        return "browser"
    return "unknown"


def accounts(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = data.get("accounts", [])
    return rows if isinstance(rows, list) else []


def transactions(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = data.get("transactions", [])
    return rows if isinstance(rows, list) else []


def loans(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = data.get("loans", [])
    return rows if isinstance(rows, list) else []


def price_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = data.get("price_index", data.get("prices", []))
    return rows if isinstance(rows, list) else []


def settings(data: Dict[str, Any]) -> Dict[str, Any]:
    row = data.get("settings", {})
    return row if isinstance(row, dict) else {}


def account_id(account: Dict[str, Any]) -> str:
    return str(account.get("id", "")).strip()


def account_name(account: Dict[str, Any]) -> str:
    return str(account.get("name", account_id(account))).strip() or account_id(account)


def account_type(account: Dict[str, Any]) -> str:
    return str(account.get("type", "")).strip()


def account_balance(account: Dict[str, Any]) -> float:
    return round(as_float(account.get("balance", 0.0)), 2)


def active_accounts(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [account for account in accounts(data) if account.get("active", True) is not False]


def money_supply(data: Dict[str, Any]) -> float:
    total = 0.0
    for account in active_accounts(data):
        if account_type(account).lower() == "central bank":
            continue
        total += account_balance(account)
    return round(total, 2)


def bank_reserves(data: Dict[str, Any]) -> float:
    total = 0.0
    for account in active_accounts(data):
        kind = account_type(account).lower()
        if kind in {"bank", "commercial bank"}:
            total += account_balance(account)
    return round(total, 2)


def setting_number(data: Dict[str, Any], *keys: str) -> float:
    row = settings(data)
    for key in keys:
        if key in row:
            return as_float(row.get(key))
    return 0.0


def tx_id(tx: Dict[str, Any]) -> str:
    return str(tx.get("id", "?"))


def tx_amount(tx: Dict[str, Any]) -> float:
    return round(as_float(tx.get("amount", 0.0)), 2)


def tx_from(tx: Dict[str, Any]) -> str:
    return str(tx.get("from_id", tx.get("fromId", ""))).strip()


def tx_to(tx: Dict[str, Any]) -> str:
    return str(tx.get("to_id", tx.get("toId", ""))).strip()


def tx_type(tx: Dict[str, Any]) -> str:
    return str(tx.get("type", tx.get("action", ""))).strip()


def open_loan(loan: Dict[str, Any]) -> bool:
    status = str(loan.get("status", "")).lower()
    return status not in {"closed", "paid"}


def loan_balance(loan: Dict[str, Any]) -> float:
    return round(as_float(loan.get("outstanding", loan.get("balanceDue", 0.0))), 2)


def price_total(row: Dict[str, Any]) -> float:
    return round(as_float(row.get("basket_total", row.get("price", 0.0))), 2)


def price_date(row: Dict[str, Any]) -> str:
    return str(row.get("date", "")).strip()


def latest_inflation(data: Dict[str, Any]) -> Optional[float]:
    rows = [row for row in price_rows(data) if price_total(row) > 0 and price_date(row)]
    fmt = data_format(data)
    if fmt == "browser":
        grouped: Dict[str, List[float]] = {}
        for row in rows:
            grouped.setdefault(price_date(row), []).append(price_total(row))
        dated = sorted((date, sum(values) / len(values)) for date, values in grouped.items() if values)
    else:
        dated = sorted((price_date(row), price_total(row)) for row in rows)
    if len(dated) < 2:
        return None
    previous = dated[-2][1]
    latest = dated[-1][1]
    if previous <= 0:
        return None
    return round(((latest - previous) / previous) * 100, 4)


def local_economy_checks(data: Dict[str, Any]) -> List[CheckResult]:
    checks: List[CheckResult] = []
    acct_rows = active_accounts(data)
    ids = [account_id(account) for account in acct_rows]
    duplicate_ids = sorted({item for item in ids if item and ids.count(item) > 1})
    checks.append(
        CheckResult(
            "Critical" if duplicate_ids else "OK",
            "Account IDs",
            f"Duplicate account IDs: {', '.join(duplicate_ids)}" if duplicate_ids else "All active account IDs are unique.",
        )
    )

    negatives = [
        f"{account_name(account)} ({account_id(account)}) has {account_balance(account):,.2f}"
        for account in acct_rows
        if account_type(account).lower() != "central bank" and account_balance(account) < -0.009
    ]
    checks.append(
        CheckResult(
            "Critical" if negatives else "OK",
            "Negative balances",
            "; ".join(negatives[:8]) if negatives else "No active non-central-bank account has a negative balance.",
        )
    )

    known_ids = set(ids)
    broken_refs: List[str] = []
    for tx in transactions(data):
        from_id = tx_from(tx)
        to_id = tx_to(tx)
        if from_id and from_id not in known_ids and from_id != "FED":
            broken_refs.append(f"{tx_id(tx)} from {from_id}")
        if to_id and to_id not in known_ids and to_id != "FED":
            broken_refs.append(f"{tx_id(tx)} to {to_id}")
    checks.append(
        CheckResult(
            "Warning" if broken_refs else "OK",
            "Transaction references",
            "; ".join(broken_refs[:10]) if broken_refs else "All transaction account references point to known active accounts.",
        )
    )

    bad_amounts = [tx_id(tx) for tx in transactions(data) if tx_amount(tx) <= 0]
    checks.append(
        CheckResult(
            "Warning" if bad_amounts else "OK",
            "Transaction amounts",
            f"Transactions with non-positive amounts: {', '.join(bad_amounts[:10])}" if bad_amounts else "All transaction amounts are positive.",
        )
    )

    supply = money_supply(data)
    checks.append(
        CheckResult(
            "Critical" if supply <= 0 else "OK",
            "Money supply",
            f"Current active money supply is {supply:,.2f}.",
        )
    )

    reserve_requirement = setting_number(data, "reserve_requirement", "reserveRequirement")
    reserves = bank_reserves(data)
    required_reserves = round(supply * reserve_requirement / 100, 2)
    checks.append(
        CheckResult(
            "Warning" if supply > 0 and reserves + 0.009 < required_reserves else "OK",
            "Reserve requirement",
            f"Bank reserves are {reserves:,.2f}; required reserves are {required_reserves:,.2f} at {reserve_requirement:.2f}%.",
        )
    )

    open_balances = [loan_balance(loan) for loan in loans(data) if open_loan(loan)]
    negative_loans = [str(loan.get("id", "?")) for loan in loans(data) if loan_balance(loan) < -0.009]
    if negative_loans:
        checks.append(CheckResult("Warning", "Loan balances", f"Loans with negative balances: {', '.join(negative_loans[:8])}."))
    else:
        checks.append(CheckResult("OK", "Loan balances", f"Open loan balance total is {sum(open_balances):,.2f}."))

    inflation = latest_inflation(data)
    target = setting_number(data, "inflation_target", "targetInflation")
    if inflation is None:
        checks.append(CheckResult("Info", "Inflation", "Not enough price data to calculate inflation."))
    elif inflation > target + 3:
        checks.append(CheckResult("Warning", "Inflation", f"Latest inflation is {inflation:.2f}%, above the {target:.2f}% target."))
    elif inflation < target - 3:
        checks.append(CheckResult("Info", "Inflation", f"Latest inflation is {inflation:.2f}%, below the {target:.2f}% target."))
    else:
        checks.append(CheckResult("OK", "Inflation", f"Latest inflation is {inflation:.2f}% against a {target:.2f}% target."))

    return checks


def format_checks(checks: Iterable[CheckResult]) -> str:
    return "\n".join(f"[{check.level}] {check.check}: {check.details}" for check in checks)


def economy_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "data_format": data_format(data),
        "account_count": len(active_accounts(data)),
        "transaction_count": len(transactions(data)),
        "open_loan_count": sum(1 for loan in loans(data) if open_loan(loan)),
        "price_record_count": len(price_rows(data)),
        "money_supply": money_supply(data),
        "bank_reserves": bank_reserves(data),
        "reserve_requirement_percent": setting_number(data, "reserve_requirement", "reserveRequirement"),
        "latest_inflation_percent": latest_inflation(data),
        "settings": settings(data),
    }


def codex_prompt(data_path: Path, data: Dict[str, Any], checks: List[CheckResult]) -> str:
    data_json = json.dumps(data, indent=2, sort_keys=True)
    if len(data_json) > 140_000:
        data_json = data_json[:140_000] + "\n... TRUNCATED: focus on visible data plus local checks ..."
    return textwrap.dedent(
        f"""
        You are checking a live classroom currency economy after a teacher or student entered data in the GUI.
        This is NOT a source-code review. Do not suggest code changes unless the data proves the app calculated something incorrectly.

        Use the classroom data below to verify:
        - account balances and money supply make sense
        - transfers, money creation/removal, loan creation/payment, and policy history are internally consistent
        - reserve requirement math is right
        - loan balances and statuses are plausible
        - price-index entries and inflation logic make sense
        - entries that look like typos, duplicates, impossible values, missing references, or policy mistakes

        Return a concise teacher-facing report with:
        1. Verdict: OK, Needs attention, or Critical.
        2. Math and ledger issues.
        3. Policy/economics issues.
        4. Specific GUI entries to recheck.
        5. Suggested next action.

        Rules:
        - Do not edit files.
        - Do not ask for or mention OpenAI API keys.
        - If the data is incomplete, say what data is needed.
        - Use the local deterministic checks as evidence, but do your own reasoning too.

        Data file: {data_path}

        Computed summary:
        {json.dumps(economy_summary(data), indent=2, sort_keys=True)}

        Local deterministic checks:
        {format_checks(checks)}

        Classroom economy JSON:
        ```json
        {data_json}
        ```
        """
    ).strip()


def startup_prompt(data_path: Path, data: Dict[str, Any], checks: List[CheckResult]) -> str:
    data_json = json.dumps(data, indent=2, sort_keys=True)
    if len(data_json) > 100_000:
        data_json = data_json[:100_000] + "\n... TRUNCATED: focus on visible starter data plus local checks ..."
    return textwrap.dedent(
        f"""
        You are helping a teacher start a classroom currency in the Classroom Central Bank app.
        This is NOT a source-code review. Do not suggest code changes.

        Use the classroom data below to create a practical startup plan for the teacher.
        Focus on classroom economy setup and math entered through the GUI:
        - a currency name and short symbol the class can use
        - which sample accounts to rename, delete, or add
        - reasonable starter balances or first central-bank injections
        - a simple opening policy rate, reserve requirement, inflation target, and warning threshold
        - the first few transactions or class activities to record
        - any setup mistakes or confusing starter values to recheck

        Return a concise teacher-facing report with:
        1. Starter verdict: Ready, Needs setup, or Check first.
        2. Recommended currency setup.
        3. Accounts to create or rename.
        4. Suggested starting balances and first money-supply move.
        5. First week operating plan.
        6. GUI fields or entries to update next.

        Rules:
        - Do not edit files.
        - Do not ask for or mention OpenAI API keys.
        - Keep numbers simple enough for a classroom to follow.
        - Explain when a suggestion creates new currency versus moves existing currency.
        - Use the local deterministic checks as evidence, but do your own reasoning too.

        Data file: {data_path}

        Computed summary:
        {json.dumps(economy_summary(data), indent=2, sort_keys=True)}

        Local deterministic checks:
        {format_checks(checks)}

        Classroom economy JSON:
        ```json
        {data_json}
        ```
        """
    ).strip()


def startup_chat_prompt(
    data_path: Path,
    data: Dict[str, Any],
    checks: List[CheckResult],
    history: List[Dict[str, str]],
    user_message: str,
) -> str:
    data_json = json.dumps(data, indent=2, sort_keys=True)
    if len(data_json) > 90_000:
        data_json = data_json[:90_000] + "\n... TRUNCATED: focus on visible starter data plus local checks ..."
    recent_history = history[-16:]
    return textwrap.dedent(
        f"""
        You are Codex inside a teacher-facing startup chat for the Classroom Central Bank app.
        The teacher is starting a classroom currency and expects a back-and-forth conversation.
        This is NOT a source-code review. Do not suggest code changes.

        Your job in this chat:
        - ask useful setup questions when needed, at most two questions in one reply
        - suggest currency names, short symbols, account setup, starter balances, and first transactions
        - explain whether a suggestion creates new currency or only moves existing currency
        - help the teacher decide GUI values for policy rate, reserve requirement, inflation target, and warning threshold
        - point out classroom economy data or math entries that look confusing or risky

        Rules:
        - Do not edit files.
        - Do not ask for or mention OpenAI API keys.
        - Keep the response conversational and concise.
        - Reply directly to the teacher's latest message.
        - If enough information is available, give concrete next GUI steps.
        - If information is missing, ask the next one or two setup questions.

        Data file: {data_path}

        Computed summary:
        {json.dumps(economy_summary(data), indent=2, sort_keys=True)}

        Local deterministic checks:
        {format_checks(checks)}

        Conversation so far:
        {json.dumps(recent_history, indent=2, sort_keys=True)}

        Teacher's latest message:
        {user_message}

        Classroom economy JSON:
        ```json
        {data_json}
        ```
        """
    ).strip()


def load_chat_history(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        incoming = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(incoming, list):
        return []
    history: List[Dict[str, str]] = []
    for row in incoming:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role", "")).strip()
        content = str(row.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            history.append({"role": role, "content": content})
    return history[-80:]


def write_chat_history(path: Path, history: List[Dict[str, str]]) -> None:
    path.write_text(json.dumps(history[-80:], indent=2) + "\n", encoding="utf-8")


def codex_missing_message() -> str:
    return textwrap.dedent(
        """
        Codex CLI was not found from this process.

        Install Codex, then run:
          codex login

        Choose ChatGPT/OpenAI sign-in. This project does not need an OpenAI API key.
        """
    ).strip()


def run_codex_for_text(prompt: str, running_message: str, echo: bool = True) -> Tuple[int, str]:
    codex = find_command("codex")
    if not codex:
        message = codex_missing_message()
        if echo:
            print(message)
        return 127, message

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
        "read-only",
        prompt,
    ]
    if echo:
        print(running_message)
    code, output = run_command(command, timeout=1800)
    if output and echo:
        print(output)
    if code != 0:
        hint = (
            "\nCodex did not complete successfully. If this is an auth problem, run `codex login` "
            "and choose ChatGPT/OpenAI sign-in; no API key is needed for this project."
        )
        if echo:
            print(hint)
        output = ((output or "") + "\n" + hint).strip()
    return code, output or ""


def run_codex_prompt(
    prompt: str,
    local_report: str,
    report_path: Path,
    running_message: str,
) -> int:
    code, output = run_codex_for_text(prompt, running_message)
    report = local_report + "\n\n" + (output or "")
    report_path.write_text(report + "\n", encoding="utf-8")
    return code


def review_economy(args: argparse.Namespace) -> int:
    data_path = Path(args.data_file).expanduser().resolve()
    data, error = load_data(data_path)
    if error or data is None:
        message = f"[Info] Economy data: {error}"
        print(message)
        LAST_REPORT.write_text(message + "\n", encoding="utf-8")
        return 0 if args.local_only else 1

    checks = local_economy_checks(data)
    local_report = f"[{timestamp()}] Local economy checks\n{format_checks(checks)}"
    print(local_report)
    if args.local_only:
        LAST_REPORT.write_text(local_report + "\n", encoding="utf-8")
        return 0

    prompt = codex_prompt(data_path, data, checks)
    return run_codex_prompt(
        prompt,
        local_report,
        LAST_REPORT,
        f"[{timestamp()}] Running Codex economy check with gpt-5.5 / xhigh / read-only.",
    )


def start_currency(args: argparse.Namespace) -> int:
    data_path = Path(args.data_file).expanduser().resolve()
    data, error = load_data(data_path)
    if error or data is None:
        message = f"[Info] Economy startup help: {error}"
        print(message)
        LAST_STARTUP_REPORT.write_text(message + "\n", encoding="utf-8")
        return 0 if args.local_only else 1

    checks = local_economy_checks(data)
    local_report = f"[{timestamp()}] Local startup context\n{format_checks(checks)}"
    print(local_report)
    if args.local_only:
        LAST_STARTUP_REPORT.write_text(local_report + "\n", encoding="utf-8")
        return 0

    prompt = startup_prompt(data_path, data, checks)
    return run_codex_prompt(
        prompt,
        local_report,
        LAST_STARTUP_REPORT,
        f"[{timestamp()}] Running Codex startup help with gpt-5.5 / xhigh / read-only.",
    )


def startup_chat(args: argparse.Namespace) -> int:
    data_path = Path(args.data_file).expanduser().resolve()
    chat_path = Path(args.chat_file).expanduser().resolve() if args.chat_file else STARTUP_CHAT_TRANSCRIPT
    user_message = str(args.message or "").strip()
    if not user_message:
        user_message = "Help me start my classroom currency. Please ask me what you need to know first."

    data, error = load_data(data_path)
    if error or data is None:
        response = f"[Info] Economy startup chat: {error}"
        print(response)
        LAST_STARTUP_REPORT.write_text(response + "\n", encoding="utf-8")
        return 0 if args.local_only else 1

    checks = local_economy_checks(data)
    local_report = f"[{timestamp()}] Local startup chat context\n{format_checks(checks)}"
    if not args.reply_only:
        print(local_report)
    history = load_chat_history(chat_path)

    if args.local_only:
        response = textwrap.dedent(
            f"""
            Local-only startup chat preview.

            I can see {len(active_accounts(data))} active account(s), a money supply of {money_supply(data):,.2f}, and {len(transactions(data))} transaction(s).
            Next, I would ask what grade level or class theme you want, then suggest a currency name, symbol, starter accounts, and opening balances.
            """
        ).strip()
        print(response)
        write_chat_history(chat_path, history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": response}])
        LAST_STARTUP_REPORT.write_text(local_report + "\n\n" + response + "\n", encoding="utf-8")
        return 0

    prompt = startup_chat_prompt(data_path, data, checks, history, user_message)
    code, output = run_codex_for_text(
        prompt,
        f"[{timestamp()}] Running Codex startup chat with gpt-5.5 / xhigh / read-only.",
        echo=not args.reply_only,
    )
    LAST_STARTUP_REPORT.write_text(local_report + "\n\n" + (output or "") + "\n", encoding="utf-8")
    if args.reply_only:
        print(output)
    if code == 0:
        write_chat_history(chat_path, history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": output}])
    return code


def data_snapshot(path: Path) -> Optional[Tuple[int, int]]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def watch(args: argparse.Namespace) -> int:
    data_path = Path(args.data_file).expanduser().resolve()
    print(f"[{timestamp()}] Codex economy guard is watching {data_path}. Press Ctrl+C to stop.")
    previous: Optional[Tuple[int, int]] = None
    exit_code = 0
    try:
        while True:
            current = data_snapshot(data_path)
            if current is not None and current != previous:
                previous = current
                time.sleep(max(args.debounce, 0.1))
                exit_code = review_economy(args)
            time.sleep(max(args.interval, 1.0))
    except KeyboardInterrupt:
        print(f"\n[{timestamp()}] Codex economy guard stopped.")
    return exit_code


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask Codex to check classroom economy data for math and policy mistakes.")
    parser.add_argument("--once", action="store_true", help="Run one economy check. This is the default unless --watch is used.")
    parser.add_argument("--watch", action="store_true", help="Watch the classroom data file and check it when it changes.")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between data-file watch checks.")
    parser.add_argument("--debounce", type=float, default=1.0, help="Seconds to wait after a data-file change before checking.")
    parser.add_argument("--data-file", default=str(DATA_FILE), help="Classroom economy JSON file to review.")
    parser.add_argument("--local-only", action="store_true", help="Run deterministic local economy checks without invoking Codex.")
    parser.add_argument("--economy-review", action="store_true", help="Explicitly run a Codex economy review.")
    parser.add_argument("--codex-review", action="store_true", help="Compatibility alias for --economy-review.")
    parser.add_argument("--startup-help", action="store_true", help="Ask Codex for a classroom currency startup plan.")
    parser.add_argument("--startup-chat", action="store_true", help="Send one teacher message to the Codex startup chat.")
    parser.add_argument("--chat-file", default=str(STARTUP_CHAT_TRANSCRIPT), help="JSON transcript file for startup chat.")
    parser.add_argument("--message", default="", help="Teacher message for --startup-chat.")
    parser.add_argument("--reply-only", action="store_true", help="For --startup-chat, print only Codex's reply.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.startup_chat:
        return startup_chat(args)
    if args.startup_help:
        return start_currency(args)
    if args.watch:
        return watch(args)
    return review_economy(args)


if __name__ == "__main__":
    raise SystemExit(main())
