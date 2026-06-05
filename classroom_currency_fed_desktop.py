#!/usr/bin/env python3
"""
Classroom Central Bank GUI
A desktop control panel for running a school or classroom currency.

Run with:
    python classroom_currency_fed_desktop.py

Uses only the Python standard library: tkinter, json, csv, pathlib, datetime.
Data is saved locally in classroom_central_bank_data.json next to this file.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Tkinter could not be loaded. On some Linux systems, install python3-tk, "
        "then run this program again."
    ) from exc

APP_NAME = "Classroom Central Bank"
APP_VERSION = "1.0"
DATA_FILENAME = "classroom_central_bank_data.json"

ACCOUNT_TYPES = [
    "Student",
    "Business",
    "Organization",
    "Commercial Bank",
    "Government",
    "Central Bank",
]

TRANSACTION_TYPES = [
    "Transfer",
    "Mint / Injection",
    "Tax / Sink",
    "Open Market Buy",
    "Open Market Sell",
    "Loan Creation",
    "Loan Payment",
    "Adjustment",
]


class ValidationError(Exception):
    """User-fixable data validation error."""


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def money(value: Any, symbol: str = "CB") -> str:
    try:
        amount = float(value)
    except Exception:
        amount = 0.0
    return f"{amount:,.2f} {symbol}"


def pct(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        number = 0.0
    return f"{number:.2f}%"


def parse_amount(text: Any, field_name: str = "Amount") -> float:
    cleaned = str(text).replace(",", "").strip()
    if cleaned == "":
        raise ValidationError(f"{field_name} is required.")
    try:
        amount = float(cleaned)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be a number.") from exc
    if amount <= 0:
        raise ValidationError(f"{field_name} must be greater than zero.")
    return round(amount, 2)


def parse_nonnegative_amount(text: Any, field_name: str = "Amount") -> float:
    cleaned = str(text).replace(",", "").strip()
    if cleaned == "":
        return 0.0
    try:
        amount = float(cleaned)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be a number.") from exc
    if amount < 0:
        raise ValidationError(f"{field_name} cannot be negative.")
    return round(amount, 2)


def parse_percent(text: Any, field_name: str = "Percent") -> float:
    cleaned = str(text).replace("%", "").strip()
    if cleaned == "":
        raise ValidationError(f"{field_name} is required.")
    try:
        value = float(cleaned)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be a number.") from exc
    if value < 0:
        raise ValidationError(f"{field_name} cannot be negative.")
    return round(value, 4)


def safe_id(text: str, prefix: str = "ACCT") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-]", "", text.upper().replace(" ", "_"))
    cleaned = cleaned.strip("_")
    if not cleaned:
        cleaned = f"{prefix}_{uuid.uuid4().hex[:6].upper()}"
    return cleaned[:30]


def normalize_date(value: str) -> str:
    raw = str(value).strip()
    if not raw:
        return today()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValidationError("Date must use YYYY-MM-DD format.") from exc


def deep_merge(default: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    output = dict(default)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(output.get(key), dict):
            output[key] = deep_merge(output[key], value)
        else:
            output[key] = value
    return output


class CentralBankStore:
    """Small JSON-backed data store for the classroom currency."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or app_dir() / DATA_FILENAME
        self.data: Dict[str, Any] = self.default_data()
        self.load_warning = ""
        self.load()

    @staticmethod
    def default_data() -> Dict[str, Any]:
        return {
            "app_version": APP_VERSION,
            "settings": {
                "currency_name": "ClassBucks",
                "currency_symbol": "CB",
                "policy_rate": 5.00,
                "reserve_requirement": 10.00,
                "inflation_target": 2.00,
                "money_growth_warning": 20.00,
                "notes": "Run your classroom economy like a central bank.",
            },
            "accounts": [
                {
                    "id": "FED",
                    "name": "Central Bank",
                    "type": "Central Bank",
                    "balance": 0.0,
                    "notes": "Issues or destroys currency. Not counted in money supply.",
                    "created_at": now_stamp(),
                },
                {
                    "id": "TREASURY",
                    "name": "Class Treasury",
                    "type": "Government",
                    "balance": 500.0,
                    "notes": "Budget account for teacher or class government.",
                    "created_at": now_stamp(),
                },
                {
                    "id": "BANK",
                    "name": "Class Commercial Bank",
                    "type": "Commercial Bank",
                    "balance": 1000.0,
                    "notes": "Reserve account for the class bank.",
                    "created_at": now_stamp(),
                },
                {
                    "id": "STUDENT_1",
                    "name": "Sample Student 1",
                    "type": "Student",
                    "balance": 0.0,
                    "notes": "Rename or delete this sample account.",
                    "created_at": now_stamp(),
                },
                {
                    "id": "STUDENT_2",
                    "name": "Sample Student 2",
                    "type": "Student",
                    "balance": 0.0,
                    "notes": "Rename or delete this sample account.",
                    "created_at": now_stamp(),
                },
                {
                    "id": "STORE",
                    "name": "Class Store",
                    "type": "Business",
                    "balance": 0.0,
                    "notes": "Example business account.",
                    "created_at": now_stamp(),
                },
            ],
            "transactions": [],
            "loans": [],
            "price_index": [
                {
                    "id": "PI_1",
                    "date": today(),
                    "basket_name": "Starter basket",
                    "basket_total": 100.0,
                    "notes": "Use the same basket each period to estimate inflation.",
                    "created_at": now_stamp(),
                }
            ],
            "snapshots": [],
        }

    @property
    def settings(self) -> Dict[str, Any]:
        return self.data["settings"]

    @property
    def accounts(self) -> List[Dict[str, Any]]:
        return self.data["accounts"]

    @property
    def transactions(self) -> List[Dict[str, Any]]:
        return self.data["transactions"]

    @property
    def loans(self) -> List[Dict[str, Any]]:
        return self.data["loans"]

    @property
    def price_index(self) -> List[Dict[str, Any]]:
        return self.data["price_index"]

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                incoming = json.load(handle)
            self.data = deep_merge(self.default_data(), incoming)
            self._ensure_core_accounts()
            self._coerce_numbers()
        except Exception as exc:
            backup = self.path.with_name(
                f"{self.path.stem}.broken-{datetime.now().strftime('%Y%m%d_%H%M%S')}{self.path.suffix}"
            )
            try:
                self.path.replace(backup)
                backup_status = f"The unreadable file was moved to {backup}."
                self.data = self.default_data()
                self.save()
            except Exception as move_exc:
                try:
                    shutil.copy2(self.path, backup)
                    backup_status = f"A backup copy was saved to {backup}."
                    self.data = self.default_data()
                    self.save()
                except Exception as backup_exc:
                    self.data = self.default_data()
                    self.load_warning = (
                        f"The data file could not be read, and a backup could not be created. "
                        f"The original file was left at {self.path}. "
                        f"Original error: {exc}. Backup error: {backup_exc}. Move error: {move_exc}."
                    )
                    return
            self.load_warning = (
                f"The data file could not be read, so a new one was created. "
                f"{backup_status} Original error: {exc}"
            )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2)

    def _ensure_core_accounts(self) -> None:
        ids = {account.get("id") for account in self.accounts}
        if "FED" not in ids:
            self.accounts.insert(
                0,
                {
                    "id": "FED",
                    "name": "Central Bank",
                    "type": "Central Bank",
                    "balance": 0.0,
                    "notes": "Issues or destroys currency. Not counted in money supply.",
                    "created_at": now_stamp(),
                },
            )

    def _coerce_numbers(self) -> None:
        for key in ["policy_rate", "reserve_requirement", "inflation_target", "money_growth_warning"]:
            try:
                self.settings[key] = float(self.settings.get(key, 0.0))
            except Exception:
                self.settings[key] = 0.0
        for account in self.accounts:
            try:
                account["balance"] = round(float(account.get("balance", 0.0)), 2)
            except Exception:
                account["balance"] = 0.0
        for tx in self.transactions:
            try:
                tx["amount"] = round(float(tx.get("amount", 0.0)), 2)
            except Exception:
                tx["amount"] = 0.0
        for loan in self.loans:
            for key in ["principal", "outstanding", "annual_rate", "term_periods"]:
                try:
                    loan[key] = round(float(loan.get(key, 0.0)), 4)
                except Exception:
                    loan[key] = 0.0
        for record in self.price_index:
            try:
                record["basket_total"] = round(float(record.get("basket_total", 0.0)), 2)
            except Exception:
                record["basket_total"] = 0.0

    def create_demo_reset(self) -> None:
        self.data = self.default_data()
        self.save()

    def account_by_id(self, account_id: str) -> Optional[Dict[str, Any]]:
        for account in self.accounts:
            if account.get("id") == account_id:
                return account
        return None

    def account_label(self, account_id: Optional[str]) -> str:
        if not account_id:
            return "Created / Destroyed"
        account = self.account_by_id(account_id)
        if not account:
            return str(account_id)
        return f"{account['name']} ({account['id']})"

    def account_options(self, include_central_bank: bool = False) -> List[str]:
        rows: List[str] = []
        for account in sorted(self.accounts, key=lambda x: (x.get("type", ""), x.get("name", ""))):
            if not include_central_bank and account.get("type") == "Central Bank":
                continue
            rows.append(f"{account['id']} | {account['name']} | {account['type']}")
        return rows

    @staticmethod
    def id_from_option(option: str) -> str:
        if "|" in option:
            return option.split("|", 1)[0].strip()
        return option.strip()

    def add_account(self, name: str, account_type: str, starting_balance: float, notes: str = "") -> str:
        name = name.strip()
        if not name:
            raise ValidationError("Account name is required.")
        if account_type not in ACCOUNT_TYPES:
            raise ValidationError("Choose a valid account type.")
        if account_type == "Central Bank":
            raise ValidationError("The app uses one Central Bank account: FED. Choose another account type.")
        account_id = safe_id(name, "ACCT")
        existing_ids = {account["id"] for account in self.accounts}
        base = account_id
        counter = 2
        while account_id in existing_ids:
            account_id = f"{base}_{counter}"
            counter += 1
        account = {
            "id": account_id,
            "name": name,
            "type": account_type,
            "balance": round(float(starting_balance), 2),
            "notes": notes.strip(),
            "created_at": now_stamp(),
        }
        self.accounts.append(account)
        if starting_balance > 0 and account_type != "Central Bank":
            self.record_transaction(
                tx_type="Mint / Injection",
                amount=starting_balance,
                to_id=account_id,
                from_id="FED",
                memo=f"Opening balance for {name}",
                tx_date=today(),
                policy_effect="Initial account funding",
                save_now=False,
            )
        self.save()
        return account_id

    def update_account(self, account_id: str, name: str, account_type: str, notes: str) -> None:
        account = self.account_by_id(account_id)
        if not account:
            raise ValidationError("Account not found.")
        if account_id == "FED" and account_type != "Central Bank":
            raise ValidationError("The FED account must stay as Central Bank type.")
        if account_id != "FED" and account_type == "Central Bank":
            raise ValidationError("Only the FED account should use the Central Bank type.")
        if account_type not in ACCOUNT_TYPES:
            raise ValidationError("Choose a valid account type.")
        if not name.strip():
            raise ValidationError("Account name is required.")
        account["name"] = name.strip()
        account["type"] = account_type
        account["notes"] = notes.strip()
        self.save()

    def delete_account(self, account_id: str) -> None:
        if account_id == "FED":
            raise ValidationError("The Central Bank account cannot be deleted.")
        account = self.account_by_id(account_id)
        if not account:
            raise ValidationError("Account not found.")
        if abs(float(account.get("balance", 0.0))) > 0.009:
            raise ValidationError("Only zero-balance accounts can be deleted.")
        for tx in self.transactions:
            if tx.get("from_id") == account_id or tx.get("to_id") == account_id:
                raise ValidationError("This account has transaction history, so it should be kept for audit records.")
        for loan in self.loans:
            if loan.get("borrower_id") == account_id:
                raise ValidationError("This account has loan history, so it should be kept for audit records.")
        self.data["accounts"] = [a for a in self.accounts if a.get("id") != account_id]
        self.save()

    def adjust_balance(self, account_id: Optional[str], delta: float, allow_negative: bool = False) -> None:
        if not account_id:
            return
        account = self.account_by_id(account_id)
        if not account:
            raise ValidationError(f"Account not found: {account_id}")
        if account.get("type") == "Central Bank":
            account["balance"] = 0.0
            return
        new_balance = round(float(account.get("balance", 0.0)) + float(delta), 2)
        if new_balance < -0.009 and not allow_negative:
            raise ValidationError(f"{account['name']} does not have enough funds.")
        account["balance"] = new_balance

    def record_transaction(
        self,
        tx_type: str,
        amount: float,
        from_id: Optional[str] = None,
        to_id: Optional[str] = None,
        memo: str = "",
        tx_date: Optional[str] = None,
        policy_effect: str = "",
        loan_id: str = "",
        save_now: bool = True,
    ) -> str:
        tx_date = normalize_date(tx_date or today())
        amount = round(float(amount), 2)
        if amount <= 0:
            raise ValidationError("Transaction amount must be greater than zero.")
        tx_id = f"TX_{uuid.uuid4().hex[:8].upper()}"
        transaction = {
            "id": tx_id,
            "date": tx_date,
            "created_at": now_stamp(),
            "type": tx_type,
            "from_id": from_id or "",
            "to_id": to_id or "",
            "amount": amount,
            "memo": memo.strip(),
            "policy_effect": policy_effect.strip(),
            "loan_id": loan_id,
        }
        self.transactions.append(transaction)
        if save_now:
            self.save()
        return tx_id

    def transfer(self, from_id: str, to_id: str, amount: float, memo: str = "", tx_date: Optional[str] = None) -> str:
        if from_id == to_id:
            raise ValidationError("From and To accounts must be different.")
        self.adjust_balance(from_id, -amount)
        self.adjust_balance(to_id, amount)
        tx_id = self.record_transaction(
            tx_type="Transfer",
            amount=amount,
            from_id=from_id,
            to_id=to_id,
            memo=memo,
            tx_date=tx_date,
            policy_effect="Moves existing currency. Money supply does not change.",
            save_now=False,
        )
        self.save()
        return tx_id

    def mint(self, to_id: str, amount: float, memo: str = "", tx_type: str = "Mint / Injection") -> str:
        self.adjust_balance(to_id, amount)
        tx_id = self.record_transaction(
            tx_type=tx_type,
            amount=amount,
            from_id="FED",
            to_id=to_id,
            memo=memo,
            tx_date=today(),
            policy_effect="Increases money supply.",
            save_now=False,
        )
        self.add_snapshot(f"After {tx_type.lower()}")
        self.save()
        return tx_id

    def sink(self, from_id: str, amount: float, memo: str = "", tx_type: str = "Tax / Sink") -> str:
        self.adjust_balance(from_id, -amount)
        tx_id = self.record_transaction(
            tx_type=tx_type,
            amount=amount,
            from_id=from_id,
            to_id="FED",
            memo=memo,
            tx_date=today(),
            policy_effect="Decreases money supply.",
            save_now=False,
        )
        self.add_snapshot(f"After {tx_type.lower()}")
        self.save()
        return tx_id

    def helicopter_drop(self, account_type: str, amount_each: float, memo: str = "") -> int:
        recipients = [
            account for account in self.accounts
            if account.get("type") == account_type and account.get("type") != "Central Bank"
        ]
        if not recipients:
            raise ValidationError(f"No accounts found for type: {account_type}")
        for account in recipients:
            self.adjust_balance(account["id"], amount_each)
            self.record_transaction(
                tx_type="Mint / Injection",
                amount=amount_each,
                from_id="FED",
                to_id=account["id"],
                memo=memo or f"Equal distribution to all {account_type} accounts",
                policy_effect="Increases money supply through equal distribution.",
                save_now=False,
            )
        self.add_snapshot(f"After equal distribution to {account_type}")
        self.save()
        return len(recipients)

    def update_settings(
        self,
        currency_name: str,
        currency_symbol: str,
        policy_rate: float,
        reserve_requirement: float,
        inflation_target: float,
        money_growth_warning: float,
        notes: str,
    ) -> None:
        if not currency_name.strip():
            raise ValidationError("Currency name is required.")
        if not currency_symbol.strip():
            raise ValidationError("Currency symbol is required.")
        self.settings["currency_name"] = currency_name.strip()
        self.settings["currency_symbol"] = currency_symbol.strip()[:8]
        self.settings["policy_rate"] = round(policy_rate, 4)
        self.settings["reserve_requirement"] = round(reserve_requirement, 4)
        self.settings["inflation_target"] = round(inflation_target, 4)
        self.settings["money_growth_warning"] = round(money_growth_warning, 4)
        self.settings["notes"] = notes.strip()
        self.record_transaction(
            tx_type="Adjustment",
            amount=0.01,
            from_id="FED",
            to_id="FED",
            memo="Policy settings updated",
            policy_effect="Policy changed. The 0.01 technical entry keeps an audit trail without changing balances.",
            save_now=False,
        )
        self.save()

    def create_loan(self, borrower_id: str, principal: float, annual_rate: float, term_periods: float, purpose: str) -> str:
        borrower = self.account_by_id(borrower_id)
        if not borrower:
            raise ValidationError("Borrower account not found.")
        if borrower.get("type") == "Central Bank":
            raise ValidationError("Central Bank cannot borrow from itself in this app.")
        loan_id = f"LOAN_{uuid.uuid4().hex[:8].upper()}"
        loan = {
            "id": loan_id,
            "borrower_id": borrower_id,
            "principal": round(principal, 2),
            "outstanding": round(principal, 2),
            "annual_rate": round(annual_rate, 4),
            "term_periods": round(term_periods, 2),
            "purpose": purpose.strip(),
            "created_date": today(),
            "status": "Open",
            "created_at": now_stamp(),
        }
        self.loans.append(loan)
        self.adjust_balance(borrower_id, principal)
        self.record_transaction(
            tx_type="Loan Creation",
            amount=principal,
            from_id="FED",
            to_id=borrower_id,
            memo=purpose or "New central bank loan",
            policy_effect="Increases money supply while loan is outstanding.",
            loan_id=loan_id,
            save_now=False,
        )
        self.add_snapshot("After loan creation")
        self.save()
        return loan_id

    def loan_by_id(self, loan_id: str) -> Optional[Dict[str, Any]]:
        for loan in self.loans:
            if loan.get("id") == loan_id:
                return loan
        return None

    def loan_options(self) -> List[str]:
        options: List[str] = []
        for loan in self.loans:
            borrower = self.account_label(loan.get("borrower_id"))
            options.append(
                f"{loan['id']} | {borrower} | outstanding {loan.get('outstanding', 0):,.2f}"
            )
        return options

    def pay_loan(self, loan_id: str, amount: float, memo: str = "") -> None:
        loan = self.loan_by_id(loan_id)
        if not loan:
            raise ValidationError("Loan not found.")
        if loan.get("status") == "Closed":
            raise ValidationError("This loan is already closed.")
        borrower_id = loan.get("borrower_id")
        outstanding = round(float(loan.get("outstanding", 0.0)), 2)
        payment = min(round(amount, 2), outstanding)
        if payment <= 0:
            raise ValidationError("Payment must be greater than zero.")
        self.adjust_balance(borrower_id, -payment)
        loan["outstanding"] = round(outstanding - payment, 2)
        if loan["outstanding"] <= 0.009:
            loan["outstanding"] = 0.0
            loan["status"] = "Closed"
        self.record_transaction(
            tx_type="Loan Payment",
            amount=payment,
            from_id=borrower_id,
            to_id="FED",
            memo=memo or f"Payment on {loan_id}",
            policy_effect="Decreases money supply when paid back to the central bank.",
            loan_id=loan_id,
            save_now=False,
        )
        self.add_snapshot("After loan payment")
        self.save()

    def forgive_loan(self, loan_id: str) -> None:
        loan = self.loan_by_id(loan_id)
        if not loan:
            raise ValidationError("Loan not found.")
        if loan.get("status") == "Closed":
            raise ValidationError("This loan is already closed.")
        outstanding = round(float(loan.get("outstanding", 0.0)), 2)
        loan["outstanding"] = 0.0
        loan["status"] = "Closed"
        self.record_transaction(
            tx_type="Adjustment",
            amount=max(outstanding, 0.01),
            from_id="FED",
            to_id="FED",
            memo=f"Loan forgiven: {loan_id}",
            policy_effect="Loan closed without repayment. Money remains in circulation.",
            loan_id=loan_id,
            save_now=False,
        )
        self.save()

    def add_price_record(self, basket_name: str, basket_total: float, notes: str, record_date: Optional[str] = None) -> str:
        if not basket_name.strip():
            raise ValidationError("Basket name is required.")
        record_id = f"PI_{uuid.uuid4().hex[:8].upper()}"
        record = {
            "id": record_id,
            "date": normalize_date(record_date or today()),
            "basket_name": basket_name.strip(),
            "basket_total": round(basket_total, 2),
            "notes": notes.strip(),
            "created_at": now_stamp(),
        }
        self.price_index.append(record)
        self.save()
        return record_id

    def total_money_supply(self) -> float:
        total = 0.0
        for account in self.accounts:
            if account.get("type") != "Central Bank":
                total += float(account.get("balance", 0.0))
        return round(total, 2)

    def reserves(self) -> float:
        return round(
            sum(float(account.get("balance", 0.0)) for account in self.accounts if account.get("type") == "Commercial Bank"),
            2,
        )

    def reserve_ratio(self) -> float:
        supply = self.total_money_supply()
        if supply <= 0:
            return 0.0
        return round((self.reserves() / supply) * 100, 4)

    def outstanding_loans(self) -> float:
        return round(sum(float(loan.get("outstanding", 0.0)) for loan in self.loans), 2)

    def price_records_sorted(self) -> List[Dict[str, Any]]:
        return sorted(self.price_index, key=lambda item: (item.get("date", ""), item.get("created_at", "")))

    def latest_inflation(self) -> Optional[float]:
        records = [record for record in self.price_records_sorted() if float(record.get("basket_total", 0.0)) > 0]
        if len(records) < 2:
            return None
        previous = float(records[-2].get("basket_total", 0.0))
        latest = float(records[-1].get("basket_total", 0.0))
        if previous <= 0:
            return None
        return round(((latest - previous) / previous) * 100, 4)

    def add_snapshot(self, label: str) -> None:
        self.data.setdefault("snapshots", []).append(
            {
                "date": now_stamp(),
                "label": label,
                "money_supply": self.total_money_supply(),
                "reserves": self.reserves(),
                "reserve_ratio": self.reserve_ratio(),
                "outstanding_loans": self.outstanding_loans(),
            }
        )
        self.data["snapshots"] = self.data["snapshots"][-250:]

    def account_type_totals(self) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for account in self.accounts:
            if account.get("type") == "Central Bank":
                continue
            totals[account.get("type", "Other")] = totals.get(account.get("type", "Other"), 0.0) + float(account.get("balance", 0.0))
        return {key: round(value, 2) for key, value in totals.items()}

    def audit_checks(self) -> List[Tuple[str, str, str]]:
        checks: List[Tuple[str, str, str]] = []
        ids = [account.get("id") for account in self.accounts]
        duplicate_ids = sorted({account_id for account_id in ids if ids.count(account_id) > 1})
        if duplicate_ids:
            checks.append(("Critical", "Duplicate account IDs", ", ".join(duplicate_ids)))
        else:
            checks.append(("OK", "Account IDs", "All account IDs are unique."))

        missing_core = [core for core in ["FED"] if core not in ids]
        if missing_core:
            checks.append(("Critical", "Core accounts", f"Missing core account(s): {', '.join(missing_core)}"))
        else:
            checks.append(("OK", "Core accounts", "Central Bank account exists."))

        negative_accounts = [
            f"{account.get('name')} ({money(account.get('balance'), self.settings.get('currency_symbol', 'CB'))})"
            for account in self.accounts
            if account.get("type") != "Central Bank" and float(account.get("balance", 0.0)) < -0.009
        ]
        if negative_accounts:
            checks.append(("Warning", "Negative balances", "; ".join(negative_accounts)))
        else:
            checks.append(("OK", "Negative balances", "No negative balances found."))

        known_ids = set(ids)
        broken_refs: List[str] = []
        for tx in self.transactions:
            from_id = tx.get("from_id")
            to_id = tx.get("to_id")
            if from_id and from_id not in known_ids:
                broken_refs.append(f"{tx.get('id')} from {from_id}")
            if to_id and to_id not in known_ids:
                broken_refs.append(f"{tx.get('id')} to {to_id}")
        if broken_refs:
            checks.append(("Warning", "Transaction references", "; ".join(broken_refs[:8])))
        else:
            checks.append(("OK", "Transaction references", "All transaction account references exist."))

        supply = self.total_money_supply()
        if supply <= 0:
            checks.append(("Critical", "Money supply", "Money supply is zero or negative."))
        else:
            checks.append(("OK", "Money supply", f"Current supply is {money(supply, self.settings.get('currency_symbol', 'CB'))}."))

        reserve_requirement = float(self.settings.get("reserve_requirement", 0.0))
        actual_ratio = self.reserve_ratio()
        if actual_ratio + 0.0001 < reserve_requirement:
            checks.append(
                (
                    "Warning",
                    "Reserve requirement",
                    f"Actual reserve ratio is {pct(actual_ratio)}, below requirement of {pct(reserve_requirement)}.",
                )
            )
        else:
            checks.append(
                (
                    "OK",
                    "Reserve requirement",
                    f"Actual reserve ratio is {pct(actual_ratio)}, at or above requirement of {pct(reserve_requirement)}.",
                )
            )

        inflation = self.latest_inflation()
        target = float(self.settings.get("inflation_target", 0.0))
        if inflation is None:
            checks.append(("Info", "Inflation", "Add at least two price index records to calculate inflation."))
        elif inflation > target + 2:
            checks.append(("Warning", "Inflation", f"Latest inflation is {pct(inflation)}, above target of {pct(target)}."))
        elif inflation < -2:
            checks.append(("Warning", "Deflation", f"Latest price change is {pct(inflation)}. Prices are falling."))
        else:
            checks.append(("OK", "Inflation", f"Latest inflation is {pct(inflation)} against target of {pct(target)}."))

        open_loans = [loan for loan in self.loans if loan.get("status") != "Closed"]
        if open_loans:
            checks.append(("Info", "Open loans", f"{len(open_loans)} loan(s) open, total {money(self.outstanding_loans(), self.settings.get('currency_symbol', 'CB'))}."))
        else:
            checks.append(("OK", "Open loans", "No open loans."))

        snapshots = self.data.get("snapshots", [])
        if len(snapshots) >= 2:
            prev = float(snapshots[-2].get("money_supply", 0.0))
            latest = float(snapshots[-1].get("money_supply", 0.0))
            warning_threshold = float(self.settings.get("money_growth_warning", 20.0))
            if prev > 0:
                growth = ((latest - prev) / prev) * 100
                if growth > warning_threshold:
                    checks.append(("Warning", "Money growth", f"Money supply grew {pct(growth)} since last snapshot."))
                else:
                    checks.append(("OK", "Money growth", f"Money supply changed {pct(growth)} since last snapshot."))
        else:
            checks.append(("Info", "Money growth", "Use central bank actions to create snapshots for growth checks."))
        return checks

    def export_csvs(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self._write_csv(directory / "accounts.csv", self.accounts)
        self._write_csv(directory / "transactions.csv", self.transactions)
        self._write_csv(directory / "loans.csv", self.loans)
        self._write_csv(directory / "price_index.csv", self.price_index)
        self._write_csv(directory / "snapshots.csv", self.data.get("snapshots", []))
        settings_rows = [{"setting": key, "value": value} for key, value in self.settings.items()]
        self._write_csv(directory / "settings.csv", settings_rows)

    @staticmethod
    def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
        fieldnames: List[str] = []
        for row in rows:
            for key in row.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
        if not fieldnames:
            fieldnames = ["empty"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)


class ScrollableText(ttk.Frame):
    def __init__(self, parent: tk.Misc, **text_kwargs: Any) -> None:
        super().__init__(parent)
        self.text = tk.Text(self, wrap="word", **text_kwargs)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)


class ClassroomCentralBankApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1220x780")
        self.root.minsize(1050, 680)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self.store = CentralBankStore()
        self.status_var = tk.StringVar(value="Ready")
        self.metric_vars: Dict[str, tk.StringVar] = {}
        self.account_form_vars: Dict[str, tk.StringVar] = {}
        self.policy_vars: Dict[str, tk.StringVar] = {}
        self.selected_account_id = tk.StringVar(value="")
        self.selected_loan_id = tk.StringVar(value="")
        self.codex_status_var = tk.StringVar(value="Codex economy check: waiting for classroom data changes.")
        self.codex_check_after_id: Optional[str] = None
        self.codex_check_running = False
        self.codex_check_pending_reason = ""

        self._setup_styles()
        self._build_shell()
        self._build_dashboard_tab()
        self._build_accounts_tab()
        self._build_transactions_tab()
        self._build_central_bank_tab()
        self._build_loans_tab()
        self._build_price_index_tab()
        self._build_audit_tab()
        self._build_help_tab()
        self.refresh_all()
        if self.store.load_warning:
            self.root.after(150, lambda: self.show_info(self.store.load_warning))

    def _setup_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Title.TLabel", font=("TkDefaultFont", 18, "bold"))
        style.configure("Subtitle.TLabel", font=("TkDefaultFont", 10))
        style.configure("Metric.TLabel", font=("TkDefaultFont", 16, "bold"))
        style.configure("MetricName.TLabel", font=("TkDefaultFont", 9))
        style.configure("Card.TFrame", relief="ridge", borderwidth=1, padding=12)
        style.configure("TButton", padding=6)
        style.configure("Accent.TButton", padding=6)

    def _build_shell(self) -> None:
        outer = ttk.Frame(self.root, padding=10)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="Classroom Central Bank", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        self.header_subtitle = ttk.Label(header, text="", style="Subtitle.TLabel")
        self.header_subtitle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Button(header, text="Save Now", command=self.save_now).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(header, text="Open Data Folder", command=self.open_data_folder).grid(row=0, column=3, padx=(8, 0))

        self.notebook = ttk.Notebook(outer)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        status = ttk.Frame(outer)
        status.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

    def _make_tab(self, title: str) -> ttk.Frame:
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=title)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        return frame

    def _build_dashboard_tab(self) -> None:
        tab = self._make_tab("Dashboard")
        container = ttk.Frame(tab)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        metrics = ttk.Frame(container)
        metrics.grid(row=0, column=0, sticky="ew")
        for col in range(5):
            metrics.columnconfigure(col, weight=1)

        for idx, key in enumerate(["money_supply", "reserves", "reserve_ratio", "inflation", "loans"]):
            card = ttk.Frame(metrics, style="Card.TFrame")
            card.grid(row=0, column=idx, sticky="ew", padx=4, pady=4)
            name = {
                "money_supply": "Money Supply",
                "reserves": "Bank Reserves",
                "reserve_ratio": "Reserve Ratio",
                "inflation": "Latest Inflation",
                "loans": "Outstanding Loans",
            }[key]
            self.metric_vars[key] = tk.StringVar(value="")
            ttk.Label(card, text=name, style="MetricName.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Label(card, textvariable=self.metric_vars[key], style="Metric.TLabel").grid(row=1, column=0, sticky="w", pady=(5, 0))

        charts = ttk.LabelFrame(container, text="Economy at a glance", padding=8)
        charts.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
        charts.columnconfigure(0, weight=1)
        charts.rowconfigure(0, weight=1)
        self.dashboard_canvas = tk.Canvas(charts, height=230, background="white", highlightthickness=1, highlightbackground="#cccccc")
        self.dashboard_canvas.grid(row=0, column=0, sticky="nsew")
        self.dashboard_canvas.bind("<Configure>", lambda _event: self.draw_dashboard_chart())

        bottom = ttk.Frame(container)
        bottom.grid(row=2, column=0, sticky="nsew")
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.rowconfigure(0, weight=1)

        recent_frame = ttk.LabelFrame(bottom, text="Recent transactions", padding=8)
        recent_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        recent_frame.columnconfigure(0, weight=1)
        recent_frame.rowconfigure(0, weight=1)
        self.recent_tx_tree = self._tree(recent_frame, ["Date", "Type", "From", "To", "Amount"], height=9)
        self.recent_tx_tree.grid(row=0, column=0, sticky="nsew")

        audit_frame = ttk.LabelFrame(bottom, text="Audit alerts", padding=8)
        audit_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        audit_frame.columnconfigure(0, weight=1)
        audit_frame.rowconfigure(0, weight=1)
        self.audit_summary_tree = self._tree(audit_frame, ["Status", "Check", "Message"], height=9)
        self.audit_summary_tree.grid(row=0, column=0, sticky="nsew")

    def _build_accounts_tab(self) -> None:
        tab = self._make_tab("Accounts")
        paned = ttk.PanedWindow(tab, orient="horizontal")
        paned.grid(row=0, column=0, sticky="nsew")

        left = ttk.Frame(paned, padding=(0, 0, 8, 0))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.accounts_tree = self._tree(left, ["ID", "Name", "Type", "Balance", "Notes"], height=20)
        self.accounts_tree.grid(row=0, column=0, sticky="nsew")
        self.accounts_tree.bind("<<TreeviewSelect>>", self.on_account_select)
        paned.add(left, weight=3)

        right = ttk.Frame(paned, padding=(8, 0, 0, 0))
        right.columnconfigure(1, weight=1)
        paned.add(right, weight=2)

        ttk.Label(right, text="Create or edit an account", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.account_form_vars = {
            "name": tk.StringVar(),
            "type": tk.StringVar(value="Student"),
            "starting_balance": tk.StringVar(value="0"),
            "notes": tk.StringVar(),
        }
        self._field(right, 1, "Name", ttk.Entry(right, textvariable=self.account_form_vars["name"]))
        self._field(right, 2, "Type", ttk.Combobox(right, textvariable=self.account_form_vars["type"], values=ACCOUNT_TYPES, state="readonly"))
        self._field(right, 3, "Opening balance", ttk.Entry(right, textvariable=self.account_form_vars["starting_balance"]))
        self._field(right, 4, "Notes", ttk.Entry(right, textvariable=self.account_form_vars["notes"]))

        buttons = ttk.Frame(right)
        buttons.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(buttons, text="Add Account", command=self.add_account).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(buttons, text="Update Selected", command=self.update_account).grid(row=0, column=1, padx=5)
        ttk.Button(buttons, text="Delete Zero-Balance", command=self.delete_account).grid(row=0, column=2, padx=5)
        ttk.Button(buttons, text="Clear", command=self.clear_account_form).grid(row=0, column=3, padx=5)

        note = (
            "Tip: Central Bank actions create or destroy currency. Normal transfers only move existing currency. "
            "The Central Bank account itself is not counted in the money supply."
        )
        ttk.Label(right, text=note, wraplength=420, justify="left").grid(row=6, column=0, columnspan=2, sticky="ew", pady=(18, 0))

    def _build_transactions_tab(self) -> None:
        tab = self._make_tab("Transactions")
        container = ttk.Frame(tab)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        form = ttk.LabelFrame(container, text="Transfer currency between accounts", padding=10)
        form.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for col in [1, 3, 5]:
            form.columnconfigure(col, weight=1)
        self.tx_from_var = tk.StringVar()
        self.tx_to_var = tk.StringVar()
        self.tx_amount_var = tk.StringVar()
        self.tx_memo_var = tk.StringVar()
        self.tx_date_var = tk.StringVar(value=today())
        ttk.Label(form, text="From").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.tx_from_combo = ttk.Combobox(form, textvariable=self.tx_from_var, state="readonly")
        self.tx_from_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        ttk.Label(form, text="To").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.tx_to_combo = ttk.Combobox(form, textvariable=self.tx_to_var, state="readonly")
        self.tx_to_combo.grid(row=0, column=3, sticky="ew", padx=(0, 10))
        ttk.Label(form, text="Amount").grid(row=0, column=4, sticky="w", padx=(0, 5))
        ttk.Entry(form, textvariable=self.tx_amount_var, width=12).grid(row=0, column=5, sticky="ew")
        ttk.Label(form, text="Date").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(8, 0))
        ttk.Entry(form, textvariable=self.tx_date_var, width=12).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Label(form, text="Memo").grid(row=1, column=2, sticky="w", padx=(0, 5), pady=(8, 0))
        ttk.Entry(form, textvariable=self.tx_memo_var).grid(row=1, column=3, columnspan=2, sticky="ew", padx=(0, 10), pady=(8, 0))
        ttk.Button(form, text="Record Transfer", command=self.record_transfer).grid(row=1, column=5, sticky="ew", pady=(8, 0))

        history = ttk.LabelFrame(container, text="Full transaction ledger", padding=8)
        history.grid(row=1, column=0, sticky="nsew")
        history.columnconfigure(0, weight=1)
        history.rowconfigure(0, weight=1)
        columns = ["Date", "Type", "From", "To", "Amount", "Memo", "Policy effect", "ID"]
        self.tx_tree = self._tree(history, columns, height=20)
        self.tx_tree.grid(row=0, column=0, sticky="nsew")

    def _build_central_bank_tab(self) -> None:
        tab = self._make_tab("Central Bank Tools")
        container = ttk.Frame(tab)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(2, weight=1)

        policy = ttk.LabelFrame(container, text="Policy settings", padding=10)
        policy.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 8))
        policy.columnconfigure(1, weight=1)
        self.policy_vars = {
            "currency_name": tk.StringVar(),
            "currency_symbol": tk.StringVar(),
            "policy_rate": tk.StringVar(),
            "reserve_requirement": tk.StringVar(),
            "inflation_target": tk.StringVar(),
            "money_growth_warning": tk.StringVar(),
            "notes": tk.StringVar(),
        }
        self._field(policy, 0, "Currency name", ttk.Entry(policy, textvariable=self.policy_vars["currency_name"]))
        self._field(policy, 1, "Symbol", ttk.Entry(policy, textvariable=self.policy_vars["currency_symbol"]))
        self._field(policy, 2, "Policy rate %", ttk.Entry(policy, textvariable=self.policy_vars["policy_rate"]))
        self._field(policy, 3, "Reserve requirement %", ttk.Entry(policy, textvariable=self.policy_vars["reserve_requirement"]))
        self._field(policy, 4, "Inflation target %", ttk.Entry(policy, textvariable=self.policy_vars["inflation_target"]))
        self._field(policy, 5, "Money growth warning %", ttk.Entry(policy, textvariable=self.policy_vars["money_growth_warning"]))
        self._field(policy, 6, "Notes", ttk.Entry(policy, textvariable=self.policy_vars["notes"]))
        ttk.Button(policy, text="Save Policy Settings", command=self.save_policy_settings).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        mint_frame = ttk.LabelFrame(container, text="Create, remove, or distribute currency", padding=10)
        mint_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 8))
        mint_frame.columnconfigure(1, weight=1)
        self.cb_account_var = tk.StringVar()
        self.cb_amount_var = tk.StringVar()
        self.cb_memo_var = tk.StringVar()
        self.cb_drop_type_var = tk.StringVar(value="Student")
        self.cb_drop_amount_var = tk.StringVar()
        ttk.Label(mint_frame, text="Account").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.cb_account_combo = ttk.Combobox(mint_frame, textvariable=self.cb_account_var, state="readonly")
        self.cb_account_combo.grid(row=0, column=1, sticky="ew")
        ttk.Label(mint_frame, text="Amount").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Entry(mint_frame, textvariable=self.cb_amount_var).grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ttk.Label(mint_frame, text="Memo").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Entry(mint_frame, textvariable=self.cb_memo_var).grid(row=2, column=1, sticky="ew", pady=(8, 0))
        button_row = ttk.Frame(mint_frame)
        button_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(button_row, text="Mint / Inject", command=self.mint_currency).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(button_row, text="Tax / Sink", command=self.sink_currency).grid(row=0, column=1, padx=5)
        ttk.Button(button_row, text="Buy Bonds", command=self.buy_bonds).grid(row=0, column=2, padx=5)
        ttk.Button(button_row, text="Sell Bonds", command=self.sell_bonds).grid(row=0, column=3, padx=5)

        sep = ttk.Separator(mint_frame)
        sep.grid(row=4, column=0, columnspan=2, sticky="ew", pady=14)
        ttk.Label(mint_frame, text="Equal distribution").grid(row=5, column=0, columnspan=2, sticky="w")
        ttk.Label(mint_frame, text="Account type").grid(row=6, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Combobox(mint_frame, textvariable=self.cb_drop_type_var, values=[t for t in ACCOUNT_TYPES if t != "Central Bank"], state="readonly").grid(row=6, column=1, sticky="ew", pady=(8, 0))
        ttk.Label(mint_frame, text="Amount each").grid(row=7, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Entry(mint_frame, textvariable=self.cb_drop_amount_var).grid(row=7, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(mint_frame, text="Distribute to All of Type", command=self.equal_distribution).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        explainer = ttk.LabelFrame(container, text="Policy cheat sheet", padding=10)
        explainer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        explainer.columnconfigure(0, weight=1)
        text = (
            "Mint / Inject adds new currency to the economy. Tax / Sink removes currency from circulation. "
            "Buying bonds injects currency, which usually stimulates spending. Selling bonds removes currency, "
            "which usually cools spending. Raising the policy rate makes borrowing more expensive. "
            "Lowering it makes borrowing easier."
        )
        ttk.Label(explainer, text=text, wraplength=1100, justify="left").grid(row=0, column=0, sticky="ew")

        snapshot_frame = ttk.LabelFrame(container, text="Money supply snapshots", padding=8)
        snapshot_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        snapshot_frame.columnconfigure(0, weight=1)
        snapshot_frame.rowconfigure(0, weight=1)
        self.snapshot_tree = self._tree(snapshot_frame, ["Date", "Label", "Money Supply", "Reserves", "Reserve Ratio", "Outstanding Loans"], height=10)
        self.snapshot_tree.grid(row=0, column=0, sticky="nsew")

    def _build_loans_tab(self) -> None:
        tab = self._make_tab("Loans")
        container = ttk.Frame(tab)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(1, weight=1)

        create = ttk.LabelFrame(container, text="Create a central bank loan", padding=10)
        create.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 8))
        create.columnconfigure(1, weight=1)
        self.loan_borrower_var = tk.StringVar()
        self.loan_principal_var = tk.StringVar()
        self.loan_rate_var = tk.StringVar()
        self.loan_term_var = tk.StringVar(value="10")
        self.loan_purpose_var = tk.StringVar()
        ttk.Label(create, text="Borrower").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.loan_borrower_combo = ttk.Combobox(create, textvariable=self.loan_borrower_var, state="readonly")
        self.loan_borrower_combo.grid(row=0, column=1, sticky="ew")
        self._field(create, 1, "Principal", ttk.Entry(create, textvariable=self.loan_principal_var))
        self._field(create, 2, "Annual rate %", ttk.Entry(create, textvariable=self.loan_rate_var))
        self._field(create, 3, "Term periods", ttk.Entry(create, textvariable=self.loan_term_var))
        self._field(create, 4, "Purpose", ttk.Entry(create, textvariable=self.loan_purpose_var))
        ttk.Button(create, text="Create Loan", command=self.create_loan).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        pay = ttk.LabelFrame(container, text="Loan payment or forgiveness", padding=10)
        pay.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 8))
        pay.columnconfigure(1, weight=1)
        self.loan_select_var = tk.StringVar()
        self.loan_payment_var = tk.StringVar()
        self.loan_payment_memo_var = tk.StringVar()
        ttk.Label(pay, text="Loan").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.loan_select_combo = ttk.Combobox(pay, textvariable=self.loan_select_var, state="readonly")
        self.loan_select_combo.grid(row=0, column=1, sticky="ew")
        self._field(pay, 1, "Payment amount", ttk.Entry(pay, textvariable=self.loan_payment_var))
        self._field(pay, 2, "Memo", ttk.Entry(pay, textvariable=self.loan_payment_memo_var))
        ttk.Button(pay, text="Record Payment", command=self.pay_loan).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(pay, text="Forgive Selected Loan", command=self.forgive_loan).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        note = (
            "Loan creation puts new currency into circulation. Loan payments remove currency again because the money returns to the central bank."
        )
        ttk.Label(pay, text=note, wraplength=500, justify="left").grid(row=5, column=0, columnspan=2, sticky="ew", pady=(15, 0))

        loans_frame = ttk.LabelFrame(container, text="Loan book", padding=8)
        loans_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        loans_frame.columnconfigure(0, weight=1)
        loans_frame.rowconfigure(0, weight=1)
        columns = ["ID", "Borrower", "Principal", "Outstanding", "Rate", "Term", "Status", "Purpose", "Date"]
        self.loans_tree = self._tree(loans_frame, columns, height=16)
        self.loans_tree.grid(row=0, column=0, sticky="nsew")
        self.loans_tree.bind("<<TreeviewSelect>>", self.on_loan_select)

    def _build_price_index_tab(self) -> None:
        tab = self._make_tab("Price Index")
        container = ttk.Frame(tab)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        form = ttk.LabelFrame(container, text="Track the price of the same basket over time", padding=10)
        form.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        self.pi_date_var = tk.StringVar(value=today())
        self.pi_name_var = tk.StringVar(value="Class basket")
        self.pi_total_var = tk.StringVar()
        self.pi_notes_var = tk.StringVar()
        ttk.Label(form, text="Date").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(form, textvariable=self.pi_date_var, width=14).grid(row=0, column=1, sticky="w", padx=(0, 10))
        ttk.Label(form, text="Basket name").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Entry(form, textvariable=self.pi_name_var).grid(row=0, column=3, sticky="ew", padx=(0, 10))
        ttk.Label(form, text="Basket total").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Entry(form, textvariable=self.pi_total_var, width=14).grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(8, 0))
        ttk.Label(form, text="Notes").grid(row=1, column=2, sticky="w", padx=(0, 8), pady=(8, 0))
        ttk.Entry(form, textvariable=self.pi_notes_var).grid(row=1, column=3, sticky="ew", padx=(0, 10), pady=(8, 0))
        ttk.Button(form, text="Add Price Record", command=self.add_price_record).grid(row=1, column=4, sticky="ew", pady=(8, 0))

        chart_frame = ttk.LabelFrame(container, text="Price trend", padding=8)
        chart_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        chart_frame.columnconfigure(0, weight=1)
        chart_frame.rowconfigure(0, weight=1)
        self.price_canvas = tk.Canvas(chart_frame, height=220, background="white", highlightthickness=1, highlightbackground="#cccccc")
        self.price_canvas.grid(row=0, column=0, sticky="nsew")
        self.price_canvas.bind("<Configure>", lambda _event: self.draw_price_chart())

        table_frame = ttk.LabelFrame(container, text="Price index records", padding=8)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.price_tree = self._tree(table_frame, ["Date", "Basket", "Total", "Notes", "ID"], height=12)
        self.price_tree.grid(row=0, column=0, sticky="nsew")

    def _build_audit_tab(self) -> None:
        tab = self._make_tab("Audit + Reports")
        container = ttk.Frame(tab)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        buttons = ttk.Frame(container)
        buttons.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(buttons, text="Run Audit", command=self.refresh_audit).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(buttons, text="Export CSV Reports", command=self.export_csv_reports).grid(row=0, column=1, padx=5)
        ttk.Button(buttons, text="Create Backup", command=self.create_backup).grid(row=0, column=2, padx=5)
        ttk.Button(buttons, text="Reset Demo Data", command=self.reset_demo_data).grid(row=0, column=3, padx=5)
        ttk.Button(buttons, text="Run Codex Economy Check", command=self.run_codex_economy_check).grid(row=0, column=4, padx=5)

        audit_frame = ttk.LabelFrame(container, text="Audit checks", padding=8)
        audit_frame.grid(row=1, column=0, sticky="nsew")
        audit_frame.columnconfigure(0, weight=1)
        audit_frame.rowconfigure(0, weight=1)
        self.audit_tree = self._tree(audit_frame, ["Status", "Check", "Message"], height=18)
        self.audit_tree.grid(row=0, column=0, sticky="nsew")

        details = ttk.LabelFrame(container, text="Data and Codex economy checks", padding=8)
        details.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        details.columnconfigure(0, weight=1)
        self.data_file_var = tk.StringVar()
        ttk.Label(details, textvariable=self.data_file_var, wraplength=1100, justify="left").grid(row=0, column=0, sticky="w")
        ttk.Label(details, textvariable=self.codex_status_var, wraplength=1100, justify="left").grid(row=1, column=0, sticky="w", pady=(6, 0))

    def _build_help_tab(self) -> None:
        tab = self._make_tab("How to Use")
        help_box = ScrollableText(tab, height=20)
        help_box.grid(row=0, column=0, sticky="nsew")
        help_text = f"""
{APP_NAME}

This app is a classroom version of a central bank dashboard. It lets you run a made-up currency with accounts, transactions, monetary policy, lending, price tracking, and audit checks.

Suggested setup
1. Rename the sample accounts or add everyone in the class as a Student account.
2. Decide the currency name and symbol on the Central Bank Tools tab.
3. Set a starting money supply by giving accounts opening balances or using Mint / Inject.
4. Record normal classroom payments on the Transactions tab.
5. Use Central Bank Tools when you want to change the whole economy.

What the tools mean
Mint / Inject: Creates new currency and adds it to an account. Money supply increases.
Tax / Sink: Removes currency from an account and destroys it. Money supply decreases.
Buy Bonds: The central bank buys something from an account, so that account receives new money. Money supply increases.
Sell Bonds: The central bank sells something to an account, so that account pays money back. Money supply decreases.
Equal Distribution: Gives the same new amount to every account of a selected type.
Policy Rate: The official interest rate. Higher rates make borrowing less attractive. Lower rates make borrowing easier.
Reserve Requirement: The percentage of the money supply that the commercial bank should hold as reserves.
Inflation Target: Your goal for price growth between price index records.

Loans
Creating a loan adds currency to the borrower and records outstanding debt. Paying the loan back removes that currency from circulation. This is a simple classroom model, not a real banking model.

Price Index
Pick a small basket of class items, such as pencil, snack, homework pass, extra free time, and track the total price over time. The app calculates inflation from the latest two records.

Audit tab
Run Audit checks to find weird things, like negative balances, missing accounts, reserve problems, or inflation above target.

Data
The app saves automatically to:
{self.store.path}

You can export CSV reports from the Audit + Reports tab. Those files can be opened in Excel, Google Sheets, or Numbers.
""".strip()
        help_box.text.insert("1.0", help_text)
        help_box.text.configure(state="disabled")

    def _field(self, parent: tk.Misc, row: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        widget.grid(row=row, column=1, sticky="ew", pady=(6, 0))

    def _tree(self, parent: tk.Misc, columns: List[str], height: int = 10) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=0, sticky="nsew")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        for col in columns:
            tree.heading(col, text=col)
            width = 120
            if col in ["Message", "Memo", "Policy effect", "Notes", "Purpose"]:
                width = 240
            if col in ["ID"]:
                width = 110
            tree.column(col, width=width, anchor="w")
        return tree

    def show_error(self, message: str) -> None:
        self.status_var.set(message)
        messagebox.showerror("Classroom Central Bank", message)

    def show_info(self, message: str) -> None:
        self.status_var.set(message)
        messagebox.showinfo("Classroom Central Bank", message)

    def save_now(self) -> None:
        self.store.save()
        self.status_var.set(f"Saved at {now_stamp()}")

    def open_data_folder(self) -> None:
        folder = self.store.path.parent
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f"open {str(folder)!r}")
            else:
                os.system(f"xdg-open {str(folder)!r}")
        except Exception:
            self.show_info(f"Data folder: {folder}")

    def refresh_all(self) -> None:
        self.refresh_header()
        self.refresh_account_options()
        self.refresh_dashboard()
        self.refresh_accounts()
        self.refresh_transactions()
        self.refresh_policy_form()
        self.refresh_snapshots()
        self.refresh_loans()
        self.refresh_price_index()
        self.refresh_audit()
        self.data_file_var.set(f"Data file: {self.store.path}")

    def refresh_header(self) -> None:
        settings = self.store.settings
        self.header_subtitle.configure(
            text=f"{settings.get('currency_name')} ({settings.get('currency_symbol')}) | Data file: {self.store.path}"
        )

    def refresh_account_options(self) -> None:
        options = self.store.account_options(include_central_bank=False)
        for combo_name in [
            "tx_from_combo",
            "tx_to_combo",
            "cb_account_combo",
            "loan_borrower_combo",
        ]:
            combo = getattr(self, combo_name, None)
            if combo is not None:
                combo.configure(values=options)
        if options:
            for var in [self.tx_from_var, self.tx_to_var, self.cb_account_var, self.loan_borrower_var]:
                if var.get() not in options:
                    var.set(options[0])
        loan_options = self.store.loan_options()
        if hasattr(self, "loan_select_combo"):
            self.loan_select_combo.configure(values=loan_options)
            if loan_options and self.loan_select_var.get() not in loan_options:
                self.loan_select_var.set(loan_options[0])
            elif not loan_options:
                self.loan_select_var.set("")

    def refresh_dashboard(self) -> None:
        symbol = self.store.settings.get("currency_symbol", "CB")
        inflation = self.store.latest_inflation()
        self.metric_vars["money_supply"].set(money(self.store.total_money_supply(), symbol))
        self.metric_vars["reserves"].set(money(self.store.reserves(), symbol))
        self.metric_vars["reserve_ratio"].set(pct(self.store.reserve_ratio()))
        self.metric_vars["inflation"].set("Need 2 records" if inflation is None else pct(inflation))
        self.metric_vars["loans"].set(money(self.store.outstanding_loans(), symbol))
        self.draw_dashboard_chart()

        self._clear_tree(self.recent_tx_tree)
        for tx in list(reversed(self.store.transactions))[:10]:
            self.recent_tx_tree.insert(
                "",
                "end",
                values=(
                    tx.get("date"),
                    tx.get("type"),
                    self.store.account_label(tx.get("from_id")),
                    self.store.account_label(tx.get("to_id")),
                    money(tx.get("amount"), symbol),
                ),
            )
        self._clear_tree(self.audit_summary_tree)
        for status, check, message in self.store.audit_checks():
            if status != "OK":
                self.audit_summary_tree.insert("", "end", values=(status, check, message))

    def draw_dashboard_chart(self) -> None:
        if not hasattr(self, "dashboard_canvas"):
            return
        canvas = self.dashboard_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 800)
        height = max(canvas.winfo_height(), 220)
        margin = 36
        symbol = self.store.settings.get("currency_symbol", "CB")
        totals = self.store.account_type_totals()
        if not totals:
            canvas.create_text(width / 2, height / 2, text="No account balances yet.")
            return
        canvas.create_text(margin, 18, text="Money by account type", anchor="w", font=("TkDefaultFont", 11, "bold"))
        chart_left = margin
        chart_top = 45
        chart_width = width - margin * 2
        chart_height = height - 82
        max_value = max(max(totals.values()), 1)
        bar_area = chart_width / max(len(totals), 1)
        for idx, (account_type, value) in enumerate(totals.items()):
            x0 = chart_left + idx * bar_area + 12
            x1 = chart_left + (idx + 1) * bar_area - 12
            bar_height = (value / max_value) * chart_height
            y0 = chart_top + chart_height - bar_height
            y1 = chart_top + chart_height
            canvas.create_rectangle(x0, y0, x1, y1, fill="#8fb8de", outline="#557a9e")
            canvas.create_text((x0 + x1) / 2, y0 - 10, text=f"{value:,.0f}", anchor="s")
            label = account_type if len(account_type) <= 15 else account_type[:14] + "..."
            canvas.create_text((x0 + x1) / 2, y1 + 16, text=label, anchor="n")
        canvas.create_text(
            width - margin,
            18,
            text=f"Total supply: {money(self.store.total_money_supply(), symbol)}",
            anchor="e",
        )

    def refresh_accounts(self) -> None:
        symbol = self.store.settings.get("currency_symbol", "CB")
        self._clear_tree(self.accounts_tree)
        for account in sorted(self.store.accounts, key=lambda a: (a.get("type", ""), a.get("name", ""))):
            self.accounts_tree.insert(
                "",
                "end",
                iid=account.get("id"),
                values=(
                    account.get("id"),
                    account.get("name"),
                    account.get("type"),
                    money(account.get("balance"), symbol),
                    account.get("notes", ""),
                ),
            )

    def refresh_transactions(self) -> None:
        symbol = self.store.settings.get("currency_symbol", "CB")
        self._clear_tree(self.tx_tree)
        for tx in reversed(self.store.transactions):
            self.tx_tree.insert(
                "",
                "end",
                values=(
                    tx.get("date"),
                    tx.get("type"),
                    self.store.account_label(tx.get("from_id")),
                    self.store.account_label(tx.get("to_id")),
                    money(tx.get("amount"), symbol),
                    tx.get("memo", ""),
                    tx.get("policy_effect", ""),
                    tx.get("id", ""),
                ),
            )

    def refresh_policy_form(self) -> None:
        settings = self.store.settings
        self.policy_vars["currency_name"].set(str(settings.get("currency_name", "ClassBucks")))
        self.policy_vars["currency_symbol"].set(str(settings.get("currency_symbol", "CB")))
        self.policy_vars["policy_rate"].set(str(settings.get("policy_rate", 0.0)))
        self.policy_vars["reserve_requirement"].set(str(settings.get("reserve_requirement", 0.0)))
        self.policy_vars["inflation_target"].set(str(settings.get("inflation_target", 0.0)))
        self.policy_vars["money_growth_warning"].set(str(settings.get("money_growth_warning", 20.0)))
        self.policy_vars["notes"].set(str(settings.get("notes", "")))
        self.loan_rate_var.set(str(settings.get("policy_rate", 0.0)))

    def refresh_snapshots(self) -> None:
        symbol = self.store.settings.get("currency_symbol", "CB")
        self._clear_tree(self.snapshot_tree)
        for snap in reversed(self.store.data.get("snapshots", [])):
            self.snapshot_tree.insert(
                "",
                "end",
                values=(
                    snap.get("date"),
                    snap.get("label"),
                    money(snap.get("money_supply"), symbol),
                    money(snap.get("reserves"), symbol),
                    pct(snap.get("reserve_ratio")),
                    money(snap.get("outstanding_loans"), symbol),
                ),
            )

    def refresh_loans(self) -> None:
        symbol = self.store.settings.get("currency_symbol", "CB")
        self._clear_tree(self.loans_tree)
        for loan in reversed(self.store.loans):
            self.loans_tree.insert(
                "",
                "end",
                iid=loan.get("id"),
                values=(
                    loan.get("id"),
                    self.store.account_label(loan.get("borrower_id")),
                    money(loan.get("principal"), symbol),
                    money(loan.get("outstanding"), symbol),
                    pct(loan.get("annual_rate")),
                    loan.get("term_periods"),
                    loan.get("status"),
                    loan.get("purpose", ""),
                    loan.get("created_date"),
                ),
            )
        self.refresh_account_options()

    def refresh_price_index(self) -> None:
        symbol = self.store.settings.get("currency_symbol", "CB")
        self._clear_tree(self.price_tree)
        for record in reversed(self.store.price_records_sorted()):
            self.price_tree.insert(
                "",
                "end",
                iid=record.get("id"),
                values=(
                    record.get("date"),
                    record.get("basket_name"),
                    money(record.get("basket_total"), symbol),
                    record.get("notes", ""),
                    record.get("id"),
                ),
            )
        self.draw_price_chart()

    def draw_price_chart(self) -> None:
        if not hasattr(self, "price_canvas"):
            return
        canvas = self.price_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 800)
        height = max(canvas.winfo_height(), 200)
        margin = 42
        records = [record for record in self.store.price_records_sorted() if float(record.get("basket_total", 0.0)) > 0]
        canvas.create_text(margin, 18, text="Basket total over time", anchor="w", font=("TkDefaultFont", 11, "bold"))
        if len(records) < 2:
            canvas.create_text(width / 2, height / 2, text="Add at least two price records to draw a trend.")
            return
        values = [float(record.get("basket_total", 0.0)) for record in records]
        min_val = min(values)
        max_val = max(values)
        if max_val == min_val:
            max_val += 1
            min_val -= 1
        plot_left = margin
        plot_right = width - margin
        plot_top = 45
        plot_bottom = height - 38
        canvas.create_line(plot_left, plot_bottom, plot_right, plot_bottom, fill="#444444")
        canvas.create_line(plot_left, plot_top, plot_left, plot_bottom, fill="#444444")
        points: List[Tuple[float, float]] = []
        for idx, value in enumerate(values):
            x = plot_left + (plot_right - plot_left) * (idx / max(len(values) - 1, 1))
            y = plot_bottom - (plot_bottom - plot_top) * ((value - min_val) / (max_val - min_val))
            points.append((x, y))
        for i in range(len(points) - 1):
            canvas.create_line(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], fill="#557a9e", width=2)
        for (x, y), record, value in zip(points, records, values):
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#8fb8de", outline="#557a9e")
            canvas.create_text(x, y - 12, text=f"{value:,.0f}", anchor="s")
        canvas.create_text(plot_left, plot_bottom + 18, text=records[0].get("date", ""), anchor="w")
        canvas.create_text(plot_right, plot_bottom + 18, text=records[-1].get("date", ""), anchor="e")
        inflation = self.store.latest_inflation()
        if inflation is not None:
            canvas.create_text(plot_right, 18, text=f"Latest inflation: {pct(inflation)}", anchor="e")

    def refresh_audit(self) -> None:
        self._clear_tree(self.audit_tree)
        for status, check, message in self.store.audit_checks():
            self.audit_tree.insert("", "end", values=(status, check, message))
        if hasattr(self, "audit_summary_tree"):
            self._clear_tree(self.audit_summary_tree)
            for status, check, message in self.store.audit_checks():
                if status != "OK":
                    self.audit_summary_tree.insert("", "end", values=(status, check, message))

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)

    def selected_tree_id(self, tree: ttk.Treeview) -> Optional[str]:
        selected = tree.selection()
        if not selected:
            return None
        return selected[0]

    def on_account_select(self, _event: Any = None) -> None:
        account_id = self.selected_tree_id(self.accounts_tree)
        if not account_id:
            return
        account = self.store.account_by_id(account_id)
        if not account:
            return
        self.selected_account_id.set(account_id)
        self.account_form_vars["name"].set(account.get("name", ""))
        self.account_form_vars["type"].set(account.get("type", "Student"))
        self.account_form_vars["starting_balance"].set(str(account.get("balance", 0.0)))
        self.account_form_vars["notes"].set(account.get("notes", ""))

    def on_loan_select(self, _event: Any = None) -> None:
        loan_id = self.selected_tree_id(self.loans_tree)
        if not loan_id:
            return
        self.selected_loan_id.set(loan_id)
        for option in self.store.loan_options():
            if option.startswith(loan_id):
                self.loan_select_var.set(option)
                break

    def add_account(self) -> None:
        try:
            starting_balance = parse_nonnegative_amount(
                self.account_form_vars["starting_balance"].get(),
                "Opening balance",
            )
            account_id = self.store.add_account(
                self.account_form_vars["name"].get(),
                self.account_form_vars["type"].get(),
                starting_balance,
                self.account_form_vars["notes"].get(),
            )
            self.clear_account_form()
            self.refresh_all()
            self.status_var.set(f"Added account {account_id}.")
            self.schedule_codex_economy_check(f"account {account_id} was added")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not add account: {exc}")

    def update_account(self) -> None:
        account_id = self.selected_account_id.get()
        if not account_id:
            self.show_error("Select an account first.")
            return
        try:
            self.store.update_account(
                account_id,
                self.account_form_vars["name"].get(),
                self.account_form_vars["type"].get(),
                self.account_form_vars["notes"].get(),
            )
            self.refresh_all()
            self.status_var.set(f"Updated account {account_id}.")
            self.schedule_codex_economy_check(f"account {account_id} was updated")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not update account: {exc}")

    def delete_account(self) -> None:
        account_id = self.selected_account_id.get()
        if not account_id:
            self.show_error("Select an account first.")
            return
        if not messagebox.askyesno("Delete account", "Delete this zero-balance account? This cannot be undone."):
            return
        try:
            self.store.delete_account(account_id)
            self.clear_account_form()
            self.refresh_all()
            self.status_var.set(f"Deleted account {account_id}.")
            self.schedule_codex_economy_check(f"account {account_id} was deleted")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not delete account: {exc}")

    def clear_account_form(self) -> None:
        self.selected_account_id.set("")
        self.account_form_vars["name"].set("")
        self.account_form_vars["type"].set("Student")
        self.account_form_vars["starting_balance"].set("0")
        self.account_form_vars["notes"].set("")
        try:
            self.accounts_tree.selection_remove(self.accounts_tree.selection())
        except Exception:
            pass

    def record_transfer(self) -> None:
        try:
            from_id = self.store.id_from_option(self.tx_from_var.get())
            to_id = self.store.id_from_option(self.tx_to_var.get())
            amount = parse_amount(self.tx_amount_var.get())
            tx_date = normalize_date(self.tx_date_var.get())
            tx_id = self.store.transfer(from_id, to_id, amount, self.tx_memo_var.get(), tx_date=tx_date)
            self.tx_amount_var.set("")
            self.tx_memo_var.set("")
            self.refresh_all()
            self.status_var.set(f"Recorded transfer {tx_id}.")
            self.schedule_codex_economy_check(f"transfer {tx_id} was recorded")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not record transfer: {exc}")

    def save_policy_settings(self) -> None:
        try:
            self.store.update_settings(
                currency_name=self.policy_vars["currency_name"].get(),
                currency_symbol=self.policy_vars["currency_symbol"].get(),
                policy_rate=parse_percent(self.policy_vars["policy_rate"].get(), "Policy rate"),
                reserve_requirement=parse_percent(self.policy_vars["reserve_requirement"].get(), "Reserve requirement"),
                inflation_target=parse_percent(self.policy_vars["inflation_target"].get(), "Inflation target"),
                money_growth_warning=parse_percent(self.policy_vars["money_growth_warning"].get(), "Money growth warning"),
                notes=self.policy_vars["notes"].get(),
            )
            self.refresh_all()
            self.status_var.set("Policy settings saved.")
            self.schedule_codex_economy_check("policy settings changed")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not save policy settings: {exc}")

    def mint_currency(self) -> None:
        try:
            account_id = self.store.id_from_option(self.cb_account_var.get())
            amount = parse_amount(self.cb_amount_var.get())
            self.store.mint(account_id, amount, self.cb_memo_var.get(), tx_type="Mint / Injection")
            self.cb_amount_var.set("")
            self.cb_memo_var.set("")
            self.refresh_all()
            self.status_var.set("Currency injected.")
            self.schedule_codex_economy_check("currency was injected")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not mint currency: {exc}")

    def sink_currency(self) -> None:
        try:
            account_id = self.store.id_from_option(self.cb_account_var.get())
            amount = parse_amount(self.cb_amount_var.get())
            self.store.sink(account_id, amount, self.cb_memo_var.get(), tx_type="Tax / Sink")
            self.cb_amount_var.set("")
            self.cb_memo_var.set("")
            self.refresh_all()
            self.status_var.set("Currency removed from circulation.")
            self.schedule_codex_economy_check("currency was removed")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not remove currency: {exc}")

    def buy_bonds(self) -> None:
        try:
            account_id = self.store.id_from_option(self.cb_account_var.get())
            amount = parse_amount(self.cb_amount_var.get())
            self.store.mint(account_id, amount, self.cb_memo_var.get() or "Central bank bond purchase", tx_type="Open Market Buy")
            self.cb_amount_var.set("")
            self.cb_memo_var.set("")
            self.refresh_all()
            self.status_var.set("Open market buy recorded.")
            self.schedule_codex_economy_check("open market buy was recorded")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not record bond purchase: {exc}")

    def sell_bonds(self) -> None:
        try:
            account_id = self.store.id_from_option(self.cb_account_var.get())
            amount = parse_amount(self.cb_amount_var.get())
            self.store.sink(account_id, amount, self.cb_memo_var.get() or "Central bank bond sale", tx_type="Open Market Sell")
            self.cb_amount_var.set("")
            self.cb_memo_var.set("")
            self.refresh_all()
            self.status_var.set("Open market sell recorded.")
            self.schedule_codex_economy_check("open market sell was recorded")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not record bond sale: {exc}")

    def equal_distribution(self) -> None:
        try:
            account_type = self.cb_drop_type_var.get()
            amount = parse_amount(self.cb_drop_amount_var.get(), "Amount each")
            count = self.store.helicopter_drop(account_type, amount, memo=f"Equal distribution to {account_type} accounts")
            self.cb_drop_amount_var.set("")
            self.refresh_all()
            self.status_var.set(f"Distributed currency to {count} {account_type} account(s).")
            self.schedule_codex_economy_check(f"currency was distributed to {account_type} accounts")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not distribute currency: {exc}")

    def create_loan(self) -> None:
        try:
            borrower_id = self.store.id_from_option(self.loan_borrower_var.get())
            principal = parse_amount(self.loan_principal_var.get(), "Principal")
            annual_rate = parse_percent(self.loan_rate_var.get(), "Annual rate")
            term = parse_amount(self.loan_term_var.get(), "Term periods")
            loan_id = self.store.create_loan(borrower_id, principal, annual_rate, term, self.loan_purpose_var.get())
            self.loan_principal_var.set("")
            self.loan_purpose_var.set("")
            self.refresh_all()
            self.status_var.set(f"Created loan {loan_id}.")
            self.schedule_codex_economy_check(f"loan {loan_id} was created")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not create loan: {exc}")

    def pay_loan(self) -> None:
        try:
            loan_id = self.store.id_from_option(self.loan_select_var.get())
            if not loan_id:
                raise ValidationError("Select a loan first.")
            amount = parse_amount(self.loan_payment_var.get(), "Payment amount")
            self.store.pay_loan(loan_id, amount, self.loan_payment_memo_var.get())
            self.loan_payment_var.set("")
            self.loan_payment_memo_var.set("")
            self.refresh_all()
            self.status_var.set(f"Recorded payment for {loan_id}.")
            self.schedule_codex_economy_check(f"loan payment was recorded for {loan_id}")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not record payment: {exc}")

    def forgive_loan(self) -> None:
        try:
            loan_id = self.store.id_from_option(self.loan_select_var.get())
            if not loan_id:
                raise ValidationError("Select a loan first.")
            if not messagebox.askyesno("Forgive loan", "Forgive this loan and close it without repayment?"):
                return
            self.store.forgive_loan(loan_id)
            self.refresh_all()
            self.status_var.set(f"Forgave loan {loan_id}.")
            self.schedule_codex_economy_check(f"loan {loan_id} was forgiven")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not forgive loan: {exc}")

    def add_price_record(self) -> None:
        try:
            total = parse_amount(self.pi_total_var.get(), "Basket total")
            record_id = self.store.add_price_record(
                basket_name=self.pi_name_var.get(),
                basket_total=total,
                notes=self.pi_notes_var.get(),
                record_date=self.pi_date_var.get(),
            )
            self.pi_total_var.set("")
            self.pi_notes_var.set("")
            self.refresh_all()
            self.status_var.set(f"Added price index record {record_id}.")
            self.schedule_codex_economy_check(f"price index record {record_id} was added")
        except ValidationError as exc:
            self.show_error(str(exc))
        except Exception as exc:
            self.show_error(f"Could not add price record: {exc}")

    def export_csv_reports(self) -> None:
        folder = filedialog.askdirectory(title="Choose a folder for CSV reports")
        if not folder:
            return
        try:
            target = Path(folder) / f"central_bank_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.store.export_csvs(target)
            self.show_info(f"CSV reports exported to:\n{target}")
        except Exception as exc:
            self.show_error(f"Could not export reports: {exc}")

    def create_backup(self) -> None:
        try:
            self.store.save()
            default_name = f"classroom_central_bank_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            target = filedialog.asksaveasfilename(
                title="Save backup as",
                defaultextension=".json",
                initialfile=default_name,
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )
            if not target:
                return
            shutil.copy2(self.store.path, target)
            self.show_info(f"Backup saved to:\n{target}")
        except Exception as exc:
            self.show_error(f"Could not create backup: {exc}")

    def reset_demo_data(self) -> None:
        if not messagebox.askyesno(
            "Reset demo data",
            "This will replace the current local data with fresh demo data. Create a backup first if you need the current economy. Continue?",
        ):
            return
        try:
            self.store.create_demo_reset()
            self.refresh_all()
            self.status_var.set("Demo data reset.")
            self.schedule_codex_economy_check("demo data was reset")
        except Exception as exc:
            self.show_error(f"Could not reset data: {exc}")

    def schedule_codex_economy_check(self, reason: str) -> None:
        self.codex_check_pending_reason = reason
        self.codex_status_var.set(f"Codex economy check queued: {reason}.")
        if self.codex_check_after_id is not None:
            try:
                self.root.after_cancel(self.codex_check_after_id)
            except Exception:
                pass
        self.codex_check_after_id = self.root.after(1800, lambda: self.run_codex_economy_check(manual=False))

    def run_codex_economy_check(self, manual: bool = True) -> None:
        guard = app_dir() / "codex_guard.py"
        if not guard.exists():
            self.show_error(f"Codex guard was not found at {guard}.")
            return

        if self.codex_check_running:
            self.codex_check_pending_reason = self.codex_check_pending_reason or "new classroom data"
            self.codex_status_var.set("Codex economy check is already running; another check will run afterward.")
            if manual:
                self.show_info("Codex economy check is already running. Another check will run afterward if data changed.")
            return

        reason = self.codex_check_pending_reason or ("manual review" if manual else "classroom data changed")
        self.codex_check_pending_reason = ""
        self.codex_check_after_id = None
        self.codex_check_running = True
        self.store.save()
        self.codex_status_var.set(f"Codex economy check running for {reason}.")
        self.status_var.set("Codex economy check started. This can take a few minutes.")

        def worker() -> None:
            try:
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(guard),
                        "--once",
                        "--economy-review",
                        "--data-file",
                        str(self.store.path),
                    ],
                    cwd=str(app_dir()),
                    text=True,
                    capture_output=True,
                    timeout=1800,
                )
                output = ((completed.stdout or "") + (completed.stderr or "")).strip()
                report = app_dir() / "codex_guard_last_run.txt"
                report.write_text(output + "\n", encoding="utf-8")
                self.root.after(0, lambda: self.finish_codex_economy_check(completed.returncode, report, output, manual))
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda: self.finish_codex_economy_check(1, app_dir() / "codex_guard_last_run.txt", message, manual))

        threading.Thread(target=worker, daemon=True).start()

    def finish_codex_economy_check(self, returncode: int, report: Path, output: str, manual: bool) -> None:
        self.codex_check_running = False
        if returncode == 0:
            self.refresh_all()
            self.codex_status_var.set(f"Codex economy check finished at {now_stamp()}. Report: {report}")
            self.status_var.set("Codex economy check finished.")
            if manual:
                self.show_info(f"Codex economy check finished.\n\nReport:\n{report}")
            if self.codex_check_pending_reason:
                self.schedule_codex_economy_check(self.codex_check_pending_reason)
            return

        summary = output[-1200:] if output else "No output was captured."
        message = (
            "Codex economy check did not finish successfully. "
            "Run `codex login` and choose ChatGPT/OpenAI sign-in if authentication is needed. "
            "This project does not need an API key. "
            f"Report: {report}"
        )
        self.codex_status_var.set(message)
        self.status_var.set("Codex economy check did not finish.")
        if manual:
            self.show_error(f"{message}\n\nLast output:\n{summary}")
        if self.codex_check_pending_reason:
            self.schedule_codex_economy_check(self.codex_check_pending_reason)


def main() -> None:
    root = tk.Tk()
    app = ClassroomCentralBankApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
