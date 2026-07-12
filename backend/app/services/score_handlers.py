"""Score-engine event handlers — ready to wire into Track 1's event bus.

Track 1 owns ``app/services/events.py`` (the ``emit`` / ``on`` bus) and the
``app/services/handlers/`` package. This module deliberately does **not** import
the bus at module load, so it is safe to ship before the bus exists. When the
bus lands, its loader wires these handlers with a single call:

    from app.services.score_handlers import register as register_score_handlers
    register_score_handlers(on)   # `on` is app.services.events.on

Each handler recomputes and upserts today's organization + department score
snapshots after any change that can move a score, then best-effort emits a
``score.updated`` event for the live ticker (skipped silently if the bus is not
present). Handlers flush; the router/bus owns the commit.
"""

from sqlalchemy.orm import Session

from app.services.score_engine import snapshot_scores

# Domain events that can move an ESG score (see the Track 1 event catalog).
RECOMPUTE_EVENTS = (
    "carbon.txn.created",
    "participation.approved",
    "compliance.issue.created",
    "compliance.issue.status_changed",
)


def handle_recompute(db: Session, event=None) -> None:
    """Recompute + snapshot org/department scores after a scoreable change."""
    org = snapshot_scores(db)
    _emit_score_updated(db, event, org)


def _emit_score_updated(db: Session, event, org) -> None:
    """Best-effort ``score.updated`` emission; no-op until Track 1's bus exists."""
    try:
        from app.services.events import Event, emit
    except Exception:
        return

    dept_id = getattr(event, "department_id", None) if event is not None else None
    dept_payload = None
    if dept_id is not None:
        for d in org.departments:
            if d.department_id == dept_id:
                dept_payload = {
                    "env": d.environmental,
                    "social": d.social,
                    "gov": d.governance,
                    "total": round(d.total, 1),
                }
                break

    emit(
        db,
        Event(
            type="score.updated",
            payload={"dept": dept_payload, "org_total": round(org.total, 1)},
            department_id=dept_id,
            entity_type="OrgScore",
        ),
    )


def register(on) -> None:
    """Register score handlers against Track 1's ``on(event_type)`` decorator."""
    for event_type in RECOMPUTE_EVENTS:
        on(event_type)(handle_recompute)
