"""Score-engine event handlers.

Registered on the domain event bus (``app/services/events.py``). Any change that
can move an ESG score triggers a full organization + department recompute and
snapshot, then emits ``score.updated`` for the live activity feed. Handlers
flush; the request/bus owns the commit.
"""

from sqlalchemy.orm import Session

from app.models.events import DomainEvent
from app.services.events import emit, handles
from app.services.score_engine import snapshot_scores


@handles("carbon.txn.created")
@handles("participation.approved")
@handles("compliance.issue.created")
@handles("compliance.issue.status_changed")
def recompute_scores(db: Session, event: DomainEvent) -> None:
    org = snapshot_scores(db)

    dept_id = event.department_id
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

    # score.updated has no downstream handlers, so this does not recurse.
    emit(
        db,
        "score.updated",
        department_id=dept_id,
        entity_type="OrgScore",
        payload={"dept": dept_payload, "org_total": round(org.total, 1)},
    )
