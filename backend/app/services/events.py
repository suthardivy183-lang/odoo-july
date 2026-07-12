from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.events import DomainEvent

EventHandler = Callable[[Session, DomainEvent], None]
_handlers: dict[str, list[EventHandler]] = defaultdict(list)


class EventBroadcaster:
    """Small committed-event ring buffer; an SSE adapter can consume this later."""

    def __init__(self, maxlen: int = 1000):
        self._events: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = Lock()

    def publish(self, item: dict[str, Any]) -> None:
        with self._lock:
            self._events.append(item)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._events))[:limit]


broadcaster = EventBroadcaster()


def handles(event_type: str):
    def register(fn: EventHandler) -> EventHandler:
        if fn not in _handlers[event_type]:
            _handlers[event_type].append(fn)
        return fn

    return register


def emit(
    db: Session,
    event_type: str,
    *,
    department_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> DomainEvent:
    row = DomainEvent(
        type=event_type,
        department_id=department_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        payload=payload or {},
    )
    db.add(row)
    db.flush()
    db.info.setdefault("pending_events", []).append(
        {
            "id": row.id,
            "type": row.type,
            "department_id": row.department_id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "actor_id": row.actor_id,
            "payload": row.payload,
        }
    )
    for handler in tuple(_handlers.get(event_type, ())):
        handler(db, row)
    return row


@event.listens_for(Session, "after_commit")
def _broadcast_committed_events(db: Session) -> None:
    for item in db.info.pop("pending_events", []):
        broadcaster.publish(item)


@event.listens_for(Session, "after_rollback")
def _discard_rolled_back_events(db: Session) -> None:
    db.info.pop("pending_events", None)
