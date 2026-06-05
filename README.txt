Classroom Currency Fed Program
==============================

This package gives you two GUI versions of a central bank for your classroom currency.

1. Easiest version: browser app
-------------------------------
Open this file in Chrome, Edge, Safari, or Firefox:

    classroom_currency_fed_browser.html

It runs offline and saves data in that browser. Use Export JSON Backup before switching computers or clearing browser data.

2. Desktop version: Python app
------------------------------
Run this file with Python 3:

    classroom_currency_fed_desktop.py

Windows shortcut:

    run_windows.bat

Mac/Linux shortcut:

    run_mac_linux.sh

The Python version saves data in a local JSON file next to the app.

What the program does
---------------------
- Creates accounts for students, businesses, banks, government, and other roles
- Tracks balances and transfers
- Lets the central bank create money or remove money
- Lets you change policy settings like interest rate, reserve requirement, and inflation target
- Creates and tracks central bank loans
- Tracks a classroom price index and calculates inflation
- Runs audit checks for bad balances, reserve problems, overdue loans, and inflation warnings
- Exports CSV reports and JSON backups

Suggested project roles
-----------------------
- Fed Chair: approves policy changes
- Market Desk: records money creation and money removal
- Bank Examiner: runs audits
- Data Analyst: updates price index
- Treasury: proposes taxes, spending, or class-store policy

Good demo flow
--------------
1. Open the browser version.
2. Load demo data.
3. Check the dashboard.
4. Add a few student accounts.
5. Issue a small stimulus or reward.
6. Add new prices for the same basket a week later.
7. If inflation rises, raise the policy rate or remove currency.
8. Export the transaction ledger and explain your policy decisions.
