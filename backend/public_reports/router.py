"""Anonymous, browser-owned reports. Nothing here creates or dispatches a job."""
from __future__ import annotations

import hashlib
import io
import json
import warnings
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool

from .models import PublicReport, ReportPhoto, ReportDelivery
from .storage import report_session
from . import dbstudios
from .delivery import deliver_report

router = APIRouter(prefix='/api/public', tags=['Public reports'])
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_REQUEST_BYTES = 3 * MAX_PHOTO_BYTES + 64 * 1024
ReportKey = Annotated[str, Header(alias='X-Report-Key', min_length=32, max_length=128)]


class ReportInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    request_id: UUID
    category: Literal['cleanliness', 'facilities', 'accessibility', 'safety', 'other']
    location: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode='after')
    def coordinates_together(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Both coordinates are required.')
        return self


def owner_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def serialise(report, session):
    created = report.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delivery = session.get(ReportDelivery, report.id)
    return {
        'id': report.id, 'reference': report.reference, 'category': report.category,
        'location': report.location, 'description': report.description,
        'latitude': report.latitude, 'longitude': report.longitude,
        'status': report.status, 'created_at': created.isoformat(),
        'delivery_status': 'delivered' if delivery and delivery.delivered_at else 'pending' if delivery else 'local',
        'photo_ids': list(session.scalars(select(ReportPhoto.id).where(ReportPhoto.report_id == report.id))),
    }


def sanitise_photo(content: bytes) -> bytes:
    """Decode and re-encode images; discard EXIF, GPS, names and other metadata."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as original:
                if original.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise ValueError('Unsupported image type.')
                if original.width * original.height > 24_000_000:
                    raise ValueError('The photo is too large to process.')
                original.load()
                photo = ImageOps.exif_transpose(original).convert('RGB')
                photo.thumbnail((1600, 1600))
                output = io.BytesIO()
                photo.save(output, format='JPEG', quality=82)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise HTTPException(422, 'Use a valid JPG, PNG or WebP photo, up to 24 megapixels.') from exc


@router.post('/reports', status_code=201)
async def create_report(request: Request, x_report_key: ReportKey, response: Response):
    # Bound the raw body before multipart parsing or image decoding.
    size = 0
    chunks = []
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_REQUEST_BYTES:
            raise HTTPException(413, 'Attach up to 3 photos, no more than 8 MB each.')
        chunks.append(chunk)
    request._body = b''.join(chunks)
    async with request.form(max_files=3, max_fields=1, max_part_size=16_384) as form:
        try:
            payload = ReportInput.model_validate_json(form.get('report', ''))
        except (ValidationError, TypeError, ValueError) as exc:
            raise HTTPException(422, 'Choose a category, enter a location (3–160 characters) and describe the issue (10–2,000 characters).') from exc
        photos = form.getlist('photos')
        if len(photos) > 3 or any(not isinstance(photo, UploadFile) for photo in photos):
            raise HTTPException(422, 'Attach up to 3 photos.')
        cleaned = []
        for photo in photos:
            content = await photo.read(MAX_PHOTO_BYTES + 1)
            if len(content) > MAX_PHOTO_BYTES:
                raise HTTPException(413, 'Each photo must be 8 MB or smaller.')
            cleaned.append(sanitise_photo(content))

    owner = owner_hash(x_report_key)
    report_id = str(payload.request_id)
    fingerprint = hashlib.sha256(json.dumps(payload.model_dump(mode='json'), sort_keys=True).encode()
                                 + b''.join(hashlib.sha256(photo).digest() for photo in cleaned)).hexdigest()
    remote = dbstudios.configured()
    with report_session(write=True) as session:
        previous = session.get(PublicReport, report_id)
        if previous:
            if previous.owner_hash != owner or previous.fingerprint != fingerprint:
                raise HTTPException(409, 'This submission has already been used. Start a new report.')
            result = serialise(previous, session)
        else:
            result = None
    if result is not None:
        if remote:
            result['delivery_status'] = 'delivered' if await run_in_threadpool(deliver_report, report_id) else 'pending'
            if result['delivery_status'] == 'pending': response.status_code = 202
        return result
    with report_session(write=True) as session:
        recent = session.scalar(select(func.count()).select_from(PublicReport).where(
            PublicReport.owner_hash == owner,
            PublicReport.created_at >= datetime.now(timezone.utc) - timedelta(days=1)))
        if recent >= 20:
            raise HTTPException(429, 'You have reached the daily demo limit. Please try again tomorrow.')
        values = payload.model_dump(exclude={'request_id'})
        report = PublicReport(id=report_id, owner_hash=owner, fingerprint=fingerprint,
                              reference='PLZ-' + uuid4().hex[:12].upper(), **values)
        session.add(report)
        try:
            session.flush()
        except IntegrityError as exc:
            raise HTTPException(409, 'A submission is already being saved. Refresh My reports before retrying.') from exc
        for content in cleaned:
            session.add(ReportPhoto(id=str(uuid4()), report_id=report.id, content=content))
        session.flush()
        if remote:
            session.add(ReportDelivery(report_id=report.id, attempts=0))
            session.flush()
        result = serialise(report, session)
    if remote:
        result['delivery_status'] = 'delivered' if await run_in_threadpool(deliver_report, report_id) else 'pending'
        if result['delivery_status'] == 'pending': response.status_code = 202
    return result


@router.get('/reports')
def list_reports(x_report_key: ReportKey):
    with report_session() as session:
        reports = session.scalars(select(PublicReport).where(PublicReport.owner_hash == owner_hash(x_report_key))
                                  .order_by(PublicReport.created_at.desc()).limit(100))
        return {'reports': [serialise(report, session) for report in reports]}


@router.get('/reports/{report_id}/photos/{photo_id}')
def get_photo(report_id: UUID, photo_id: UUID, x_report_key: ReportKey):
    with report_session() as session:
        report = session.get(PublicReport, str(report_id))
        photo = session.get(ReportPhoto, str(photo_id))
        if not report or report.owner_hash != owner_hash(x_report_key) or not photo or photo.report_id != report.id:
            raise HTTPException(404, 'Photo not found.')
        return Response(photo.content, media_type='image/jpeg',
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
