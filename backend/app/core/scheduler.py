"""In-process APScheduler jobs (no external infrastructure).

- compliance overdue sweep: every 5 minutes (+ once shortly after startup)
- policy acknowledgement reminders: daily 09:00 IST (+ once shortly after startup)
- badge sweep safety net: hourly
Each job opens its own session and commits; failures are logged, never fatal.
"""

import datetime as dt
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.db.session import SessionLocal
from app.utils.time import IST

logger = logging.getLogger("ecosphere.scheduler")


def _run_with_session(fn, label: str):
    db = SessionLocal()
    try:
        result = fn(db)
        db.commit()
        if result:
            logger.info("%s: %s", label, result)
    except Exception:
        db.rollback()
        logger.exception("Scheduled job failed: %s", label)
    finally:
        db.close()


def compliance_overdue_job():
    from app.services.compliance_rules import run_overdue_check

    _run_with_session(run_overdue_check, "compliance overdue sweep")


def policy_reminder_job():
    from app.services.policy_reminders import send_policy_reminders

    _run_with_session(send_policy_reminders, "policy reminders")


def badge_sweep_job():
    from app.services.badges import sweep_all

    _run_with_session(sweep_all, "badge sweep")


def daily_risk_snapshot_job():
    from app.services.risk_engine import recalculate_all_departments

    _run_with_session(recalculate_all_departments, "daily risk snapshots")


def nightly_score_snapshot_job():
    from app.services.score_engine import run_nightly_snapshot

    _run_with_session(run_nightly_snapshot, "nightly score snapshots")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=str(IST))
    soon = dt.datetime.now(IST) + dt.timedelta(seconds=15)
    scheduler.add_job(compliance_overdue_job, IntervalTrigger(minutes=5))
    scheduler.add_job(compliance_overdue_job, DateTrigger(run_date=soon))
    scheduler.add_job(policy_reminder_job, CronTrigger(hour=9, minute=0))
    scheduler.add_job(policy_reminder_job, DateTrigger(run_date=soon + dt.timedelta(seconds=15)))
    scheduler.add_job(badge_sweep_job, IntervalTrigger(hours=1))
    scheduler.add_job(daily_risk_snapshot_job, CronTrigger(hour=0, minute=5))
    scheduler.add_job(nightly_score_snapshot_job, CronTrigger(hour=0, minute=10))
    scheduler.start()
    logger.info("Scheduler started")
    return scheduler
