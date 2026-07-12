"""Singleton organization settings accessor."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import OrgSettings
from app.models.enums import NotificationType

DEFAULT_NOTIFICATION_PREFS = {
    t.value: {"in_app": True, "email": True} for t in NotificationType
}


def get_org_settings(db: Session) -> OrgSettings:
    row = db.execute(select(OrgSettings).limit(1)).scalar_one_or_none()
    if row is None:
        row = OrgSettings(notification_prefs=dict(DEFAULT_NOTIFICATION_PREFS))
        db.add(row)
        db.flush()
    return row


def channel_prefs(settings_row: OrgSettings, ntype: NotificationType) -> dict:
    prefs = (settings_row.notification_prefs or {}).get(ntype.value)
    if not isinstance(prefs, dict):
        return {"in_app": True, "email": True}
    return {"in_app": prefs.get("in_app", True), "email": prefs.get("email", True)}
