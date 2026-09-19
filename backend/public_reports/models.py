"""Reports and sanitised photographs share the application's persistent database."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text

from sqlalchemy.dialects.mysql import MEDIUMBLOB
from .storage import ReportsBase


class PublicReport(ReportsBase):
    __tablename__ = 'pliz_public_reports'

    id = Column(String(36), primary_key=True)
    owner_hash = Column(String(64), nullable=False, index=True)
    fingerprint = Column(String(64), nullable=False)
    reference = Column(String(24), nullable=False, unique=True)
    category = Column(String(30), nullable=False)
    location = Column(String(160), nullable=False)
    description = Column(Text, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    status = Column(String(24), nullable=False, default='received')
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))


class ReportPhoto(ReportsBase):
    __tablename__ = 'pliz_public_report_photos'

    id = Column(String(36), primary_key=True)
    report_id = Column(String(36), ForeignKey('pliz_public_reports.id'), nullable=False, index=True)
    # MariaDB BLOB is limited to 64 KiB; normal phone photographs need MEDIUMBLOB.
    content = Column(LargeBinary().with_variant(MEDIUMBLOB(), 'mysql', 'mariadb'), nullable=False)


class ReportDelivery(ReportsBase):
    __tablename__ = 'pliz_public_report_deliveries'

    report_id = Column(String(36), ForeignKey('pliz_public_reports.id'), primary_key=True)
    delivered_at = Column(DateTime(timezone=True))
    attempts = Column(Integer, nullable=False, default=0)
