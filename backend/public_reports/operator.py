"""Report inbox: public in demo mode, authenticated in private deployments."""
import os
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, or_, select

from ..security import DemoGuard
from .models import PublicReport, ReportPhoto
from .router import serialise
from .storage import report_session, storage_info
from . import dbstudios


def require_operator(request: Request):
    # Local development follows the existing localhost workspace access policy.
    if os.getenv('PLIZ_ENV', 'development') != 'production':
        return
    guard: DemoGuard = request.app.state.security
    # Explicit public-demo mode opens the inbox and photos with the workspace.
    if guard.public_demo:
        return
    if not guard.username or len(guard.password) < 16:
        raise HTTPException(503, 'Operator access is not configured. Set PLIZ_AUTH_USERNAME and PLIZ_AUTH_PASSWORD on the server.')
    if not guard.authorised(request.headers.get('authorization', '')):
        raise HTTPException(401, 'Sign in to view public reports.')


router = APIRouter(prefix='/api/operator/reports', tags=['Public report inbox'],
                   dependencies=[Depends(require_operator)])


@router.get('')
def reports(q: Annotated[str, Query(max_length=160)] = '',
            category: Literal['cleanliness', 'facilities', 'accessibility', 'safety', 'other'] | None = None,
            page: Annotated[int, Query(ge=1, le=10000)] = 1):
    try:
        if dbstudios.configured():
            all_reports = dbstudios.snapshot()
            matching = [report for report in all_reports if (not category or report['category'] == category)
                        and (not q.strip() or q.strip().lower() in ' '.join([report['reference'], report['location'], report['description']]).lower())]
            return {'reports': matching[(page - 1) * 20:page * 20], 'total': len(matching), 'page': page, 'page_size': 20,
                    'summary': {'total': len(all_reports), 'received': sum(report['status'] == 'received' for report in all_reports),
                                'photos': sum(len(report['photo_ids']) for report in all_reports)},
                    'storage': {'backend': 'DBStudios API', 'destination': 'dbstudios'}}
    except dbstudios.DBStudiosError as exc:
        raise HTTPException(503, str(exc)) from None
    filters = []
    if q.strip():
        query = q.strip()
        filters.append(or_(PublicReport.reference.icontains(query, autoescape=True),
                           PublicReport.location.icontains(query, autoescape=True),
                           PublicReport.description.icontains(query, autoescape=True)))
    if category:
        filters.append(PublicReport.category == category)
    with report_session() as session:
        total = session.scalar(select(func.count()).select_from(PublicReport).where(*filters))
        records = session.scalars(select(PublicReport).where(*filters)
                                  .order_by(PublicReport.created_at.desc(), PublicReport.id)
                                  .offset((page - 1) * 20).limit(20))
        items = [serialise(record, session) for record in records]
        received = session.scalar(select(func.count()).select_from(PublicReport).where(PublicReport.status == 'received'))
        photo_count = session.scalar(select(func.count()).select_from(ReportPhoto))
        all_count = session.scalar(select(func.count()).select_from(PublicReport))
        return {'reports': items, 'total': total, 'page': page, 'page_size': 20,
                'summary': {'total': all_count, 'received': received, 'photos': photo_count},
                'storage': storage_info()}


@router.get('/{report_id}/photos/{photo_id}')
def photo(report_id: UUID, photo_id: UUID):
    with report_session() as session:
        item = session.get(ReportPhoto, str(photo_id))
        if not item or item.report_id != str(report_id):
            raise HTTPException(404, 'Photo not found.')
        return Response(item.content, media_type='image/jpeg',
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
