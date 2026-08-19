"""Persist TSDR trademark data and calculate docket deadlines."""

from __future__ import annotations

import calendar
import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from flask import current_app

from docket.models import (
    Case,
    CaseStatus,
    CaseType,
    Deadline,
    DeadlineType,
    db,
)


def parse_uspto_date(value: str | date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m-%d-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def status_to_case_status(status: str) -> CaseStatus:
    """Map the raw TSDR status to the existing CaseStatus enum."""
    normalized = (status or "").upper()
    if "DEAD" in normalized or "ABANDON" in normalized:
        return CaseStatus.ABANDONED
    if "CANCEL" in normalized:
        return CaseStatus.CANCELLATION
    if "REGISTRATION" in normalized or "REGISTERED" in normalized:
        return CaseStatus.REGISTERED
    if "NOTICE OF ALLOWANCE" in normalized or "PUBLISHED" in normalized:
        return CaseStatus.ALLOWED
    if "OFFICE ACTION" in normalized or "EXAMINATION" in normalized:
        return CaseStatus.EXAMINATION
    if "PENDING" in normalized or "AWAITING" in normalized or "PROSECUTION" in normalized:
        return CaseStatus.PENDING
    return CaseStatus.FILED


def _deadline_status(due_date: date) -> str:
    return "overdue" if due_date < date.today() else "pending"


def calculate_trademark_deadlines(data: dict[str, Any], *, office_action_months: int = 3) -> list[dict[str, Any]]:
    """Build actionable deadlines from a TSDR status snapshot.

    These are configurable docketing suggestions, not legal advice.  The
    office-action and statement-of-use periods are kept in one service so a
    firm can change its rules without changing the API client.
    """
    status = str(data.get("status") or "").upper()
    trigger_date = parse_uspto_date(data.get("status_date")) or parse_uspto_date(data.get("filing_date")) or date.today()
    deadlines: list[dict[str, Any]] = []

    if "OFFICE ACTION" in status or "ACTION" in status:
        due = add_months(trigger_date, max(1, office_action_months))
        deadlines.append({
            "deadline_type": DeadlineType.OFFICE_ACTION_RESPONSE,
            "title": "Trademark office action response",
            "description": "Review the TSDR status and prepare the response before the calculated response date.",
            "trigger_date": trigger_date,
            "due_date": due,
            "statutory_period": f"{office_action_months} months (configurable)",
        })

    if "NOTICE OF ALLOWANCE" in status or "STATEMENT OF USE" in status:
        due = add_months(trigger_date, 6)
        deadlines.append({
            "deadline_type": DeadlineType.STATEMENT_OF_USE,
            "title": "Statement of use or extension",
            "description": "Prepare the statement of use or request an available extension before the calculated date.",
            "trigger_date": trigger_date,
            "due_date": due,
            "statutory_period": "6 months (configurable)",
        })

    registration_date = parse_uspto_date(data.get("registration_date"))
    if ("REGISTRATION" in status or "REGISTERED" in status) and not registration_date:
        # TSDR responses vary by record type; status_date is the safest
        # available fallback when an explicit registration date is absent.
        registration_date = trigger_date
    if ("REGISTRATION" in status or "REGISTERED" in status) and registration_date:
        section_8_due = add_months(registration_date, 60)
        renewal_due = add_months(registration_date, 108)
        deadlines.extend([
            {
                "deadline_type": DeadlineType.SECTION_8,
                "title": "Section 8 declaration window",
                "description": "Review the Section 8 maintenance filing window for this registration.",
                "trigger_date": registration_date,
                "due_date": section_8_due,
                "statutory_period": "5 years from registration (review window)",
            },
            {
                "deadline_type": DeadlineType.RENEWAL,
                "title": "Trademark renewal window",
                "description": "Review the renewal filing window for this registration.",
                "trigger_date": registration_date,
                "due_date": renewal_due,
                "statutory_period": "9 years from registration (review window)",
            },
        ])

    return deadlines


def _case_description(data: dict[str, Any]) -> str:
    parts = []
    if data.get("owner_name"):
        parts.append(f"Owner: {data['owner_name']}")
    if data.get("goods_services"):
        parts.append(f"Goods/services: {data['goods_services']}")
    if data.get("class_numbers"):
        classes = ", ".join(str(item) for item in data["class_numbers"])
        parts.append(f"International classes: {classes}")
    return "\n".join(parts)


def sync_trademark_case(user_id: int, trademark_data: dict[str, Any]) -> int:
    """Upsert a trademark Case and its calculated deadlines."""
    serial = re.sub(r"\D", "", str(trademark_data.get("serial_number") or ""))
    if not serial:
        raise ValueError("TSDR response did not include a serial number")

    filing_date = parse_uspto_date(trademark_data.get("filing_date")) or date.today()
    case = Case.query.filter(
        Case.user_id == user_id,
        (Case.application_number == serial) | (Case.case_number == f"TM-{serial}"),
    ).first()
    if case is None:
        case = Case(
            user_id=user_id,
            case_number=f"TM-{serial}",
            application_number=serial,
            type=CaseType.TRADEMARK,
            title=trademark_data.get("mark_name") or f"Trademark {serial}",
            filing_date=filing_date,
        )
        db.session.add(case)
    else:
        case.application_number = serial
        case.filing_date = filing_date
        case.title = trademark_data.get("mark_name") or case.title or f"Trademark {serial}"

    raw_status = str(trademark_data.get("status") or "Unknown")
    case.type = CaseType.TRADEMARK
    case.status = status_to_case_status(raw_status)
    case.uspto_status = raw_status
    case.uspto_last_checked = datetime.utcnow()
    registration_date = parse_uspto_date(trademark_data.get("registration_date"))
    if registration_date:
        case.grant_date = registration_date
    case.uspto_data = json.dumps(trademark_data, default=str)
    case.description = _case_description(trademark_data)
    db.session.flush()

    calculated = calculate_trademark_deadlines(
        trademark_data,
        office_action_months=int(current_app.config.get("TRADEMARK_OFFICE_ACTION_MONTHS", 3)),
    )
    for item in calculated:
        existing = Deadline.query.filter_by(
            case_id=case.id,
            deadline_type=item["deadline_type"],
            due_date=item["due_date"],
        ).first()
        if existing is None:
            db.session.add(Deadline(
                case_id=case.id,
                deadline_type=item["deadline_type"],
                title=item["title"],
                description=item["description"],
                trigger_date=item["trigger_date"],
                due_date=item["due_date"],
                statutory_period=item["statutory_period"],
                status=_deadline_status(item["due_date"]),
            ))
        elif existing.status not in {"completed", "cancelled"}:
            existing.status = _deadline_status(existing.due_date)
            existing.description = item["description"]

    db.session.commit()
    return case.id
