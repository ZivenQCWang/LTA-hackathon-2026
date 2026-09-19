"""Durable outbox: reports survive DBStudios outages and process restarts."""
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
import logging
import threading

from sqlalchemy import select

from . import dbstudios
from .models import PublicReport, ReportDelivery
from .storage import report_session

_lock = threading.Lock()
logger = logging.getLogger(__name__)


def deliver_report(report_id):
    from .router import serialise
    if not dbstudios.configured():
        return False
    with _lock:
        with report_session() as session:
            delivery = session.get(ReportDelivery, report_id)
            if delivery and delivery.delivered_at:
                return True
            report = session.get(PublicReport, report_id)
            if not report:
                return False
            payload = serialise(report, session)
        success = False
        try:
            dbstudios.deliver(payload)
            success = True
        except dbstudios.DBStudiosError:
            logger.warning('DBStudios delivery pending; retry scheduled.')
        with report_session(write=True) as session:
            delivery = session.get(ReportDelivery, report_id)
            if not delivery:
                delivery = ReportDelivery(report_id=report_id, attempts=0)
                session.add(delivery)
            delivery.attempts += 1
            if success:
                delivery.delivered_at = datetime.now(timezone.utc)
        return success


def retry_pending():
    if not dbstudios.configured():
        return
    with report_session() as session:
        pending = list(session.scalars(select(ReportDelivery.report_id)
                                      .where(ReportDelivery.delivered_at.is_(None))
                                      .order_by(ReportDelivery.attempts).limit(5)))
    for report_id in pending:
        if not deliver_report(report_id):
            break  # Back off on outage / rate limit instead of hammering the API.


@asynccontextmanager
async def report_lifespan(app):
    async def run():
        while True:
            try:
                await asyncio.to_thread(retry_pending)
            except Exception:
                logger.warning('Report delivery retry deferred.')
            await asyncio.sleep(30)

    task = asyncio.create_task(run()) if dbstudios.configured() else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
