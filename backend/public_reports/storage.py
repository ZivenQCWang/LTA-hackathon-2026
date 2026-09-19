"""One report database shared by passenger submissions and the operator inbox.

Photographs and a durable delivery queue stay in the existing application
database. DBStudios is accessed through its supported project REST API.
"""
import logging
import os
import threading
from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from ..database import engine as workspace_engine

ReportsBase = declarative_base()
engine = workspace_engine

ReportSession = sessionmaker(engine, expire_on_commit=False)
_ready = False
_schema_lock = threading.Lock()
logger = logging.getLogger(__name__)


def initialise_reports():
    global _ready
    with _schema_lock:
        if not _ready:
            ReportsBase.metadata.create_all(engine)
            _ready = True


def storage_info():
    return {'backend': engine.dialect.name,
            'destination': 'dbstudios' if os.getenv('DBSTUDIOS_API_URL') else 'workspace_database'}


@contextmanager
def report_session(*, write=False):
    try:
        initialise_reports()
        with (ReportSession.begin() if write else ReportSession()) as session:
            yield session
    except SQLAlchemyError as exc:
        # Database exceptions can contain connection details; do not return them.
        logger.warning('Public report database request failed: %s', type(exc).__name__)
        raise HTTPException(503, 'Report storage is unavailable. Please try again shortly. No successful submission has been confirmed.') from None
