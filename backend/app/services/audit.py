"""Audit-history writer. Every mutating endpoint must record an entry.

Usage:
    before = snapshot(obj, FIELDS)
    ... mutate ...
    log_action(db, actor.id, AuditAction.update, "carbon_transaction", obj.id,
               entity_label=obj.description, before=before, after=snapshot(obj, FIELDS))

Services only flush; the router owns the transaction and commits once.
"""

import datetime as dt
import decimal
import enum
from typing import Any

from sqlalchemy.orm import Session

from app.models.core import AuditLog
from app.models.enums import AuditAction


def _json_safe(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


def snapshot(obj: Any, fields: list[str]) -> dict:
    """JSON-safe dict of the given attributes of an ORM object."""
    return {f: _json_safe(getattr(obj, f, None)) for f in fields}


def diff(before: dict | None, after: dict | None) -> tuple[dict | None, dict | None]:
    """Reduce two snapshots to only the keys that changed."""
    if not before or not after:
        return before, after
    changed = [k for k in after if before.get(k) != after.get(k)]
    return {k: before.get(k) for k in changed}, {k: after.get(k) for k in changed}


def log_action(
    db: Session,
    actor_user_id: int | None,
    action: AuditAction,
    entity_type: str,
    entity_id: int | None = None,
    entity_label: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> AuditLog:
    before_d, after_d = diff(_json_safe(before) if before else None, _json_safe(after) if after else None)
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=(entity_label or "")[:255] or None,
        before_json=before_d,
        after_json=after_d,
    )
    db.add(entry)
    return entry
