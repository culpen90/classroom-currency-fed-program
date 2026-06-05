# Classroom Currency Fed Program

This package gives you two GUI versions of a central bank for your classroom currency.

## Browser App

Open `classroom_currency_fed_browser.html` in Chrome, Edge, Safari, or Firefox.

It runs offline and saves data in that browser. Use Export JSON Backup before switching computers or clearing browser data.

## Desktop App

Run `classroom_currency_fed_desktop.py` with Python 3.

Windows shortcut:

```bat
run_windows.bat
```

Mac/Linux shortcut:

```bash
./run_mac_linux.sh
```

The Python version saves data in a local JSON file next to the app.

## OpenAI Codex Economy Check

The desktop app can ask the local Codex CLI to check the classroom economy data that people enter into the GUI. After successful account, transfer, policy, loan, money-supply, or price-index changes, the app queues a Codex economy check. Codex reviews the current JSON data with `gpt-5.5` and `model_reasoning_effort="xhigh"` to look for math mistakes, broken ledger logic, reserve shortfalls, strange loan balances, inflation issues, or entries that look like typos.

This uses the user's Codex login, not an OpenAI API key. Set it up once:

```bash
codex login
```

Choose ChatGPT/OpenAI sign-in in the browser. Do not add an API key to this project.

In the desktop app, use **Audit + Reports -> Run Codex Economy Check** to run a manual check. The latest result is saved to `codex_guard_last_run.txt`.

Manual terminal commands:

```bash
python3 codex_guard.py --once --local-only
python3 codex_guard.py --once --economy-review
python3 codex_guard.py --watch
```

On Windows, use `python` instead of `python3` if needed. The browser app cannot launch the local Codex CLI by itself, so its Audit tab can download a Codex review prompt containing the current browser data.

## What The Program Does

- Creates accounts for students, businesses, banks, government, and other roles
- Tracks balances and transfers
- Lets the central bank create money or remove money
- Lets you change policy settings like interest rate, reserve requirement, and inflation target
- Creates and tracks central bank loans
- Tracks a classroom price index and calculates inflation
- Runs audit checks for bad balances, reserve problems, overdue loans, and inflation warnings
- Runs Codex economy checks on desktop data entries using the user's Codex login
- Exports CSV reports and JSON backups

## Suggested Project Roles

- Fed Chair: approves policy changes
- Market Desk: records money creation and money removal
- Bank Examiner: runs audits
- Data Analyst: updates price index
- Treasury: proposes taxes, spending, or class-store policy

## Good Demo Flow

1. Open the browser version.
2. Load demo data.
3. Check the dashboard.
4. Add a few student accounts.
5. Issue a small stimulus or reward.
6. Add new prices for the same basket a week later.
7. If inflation rises, raise the policy rate or remove currency.
8. Export the transaction ledger and explain your policy decisions.
