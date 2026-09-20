"""DBStudios project API adapter. Credentials never reach the browser."""
import json
import os
import threading
import time
from uuid import UUID

import httpx


class DBStudiosError(Exception):
    pass


def configured():
    url, key = os.getenv('DBSTUDIOS_API_URL', '').strip(), os.getenv('DBSTUDIOS_API_KEY', '').strip()
    if bool(url) != bool(key):
        raise DBStudiosError('Configure both DBSTUDIOS_API_URL and DBSTUDIOS_API_KEY.')
    return bool(url and key)


def request(method, path, body=None):
    url = os.getenv('DBSTUDIOS_API_URL', '').rstrip('/')
    if not url.startswith('https://'):
        raise DBStudiosError('DBStudios requires an HTTPS project API URL.')
    try:
        response = httpx.request(method, url + path, json=body, timeout=15,
                                headers={'Authorization': 'Bearer ' + os.getenv('DBSTUDIOS_API_KEY', '')})
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError('Invalid DBStudios response')
        return result
    except (httpx.HTTPError, ValueError):
        # Do not expose upstream errors, URLs with credentials, or query values.
        raise DBStudiosError('DBStudios could not be reached. The saved report will be retried.') from None


def values(report):
    description = report['description']
    return {
        'report_id': report['id'], 'reference': report['reference'],
        'category': report['category'], 'location': report['location'],
        'description': description[:500], 'description_2': description[500:1000],
        'description_3': description[1000:1500], 'description_4': description[1500:2000],
        'status': report['status'], 'submitted_at': report['created_at'],
        'photo_count': len(report['photo_ids']),
        'photo_paths': json.dumps([f"/api/operator/reports/{report['id']}/photos/{pid}" for pid in report['photo_ids']]),
        # DBStudios decimal columns have two places; the text pair is lossless.
        'latitude': report['latitude'], 'longitude': report['longitude'],
        'gps_coordinates': json.dumps([report['latitude'], report['longitude']]),
    }


_snapshot = None
_snapshot_time = 0.0
_snapshot_lock = threading.RLock()


def invalidate():
    global _snapshot, _snapshot_time
    with _snapshot_lock:
        _snapshot, _snapshot_time = None, 0.0


def deliver(report):
    report_id = str(UUID(report['id']))  # The only interpolated SQL value is a validated UUID.
    existing = request('POST', '/query', {'sql': f"SELECT report_id FROM public_reports WHERE report_id = '{report_id}' LIMIT 1"})
    if not existing.get('rows'):
        request('POST', '/tables/public_reports/rows', {'values': values(report)})
    invalidate()


def decode(row):
    report_id = str(UUID(row['report_id']))
    coordinates = json.loads(row.get('gps_coordinates') or '[null,null]')
    paths = json.loads(row.get('photo_paths') or '[]')
    return {'id': report_id, 'reference': row['reference'], 'category': row['category'],
            'location': row['location'],
            'description': ''.join(row.get(field) or '' for field in ['description', 'description_2', 'description_3', 'description_4']),
            'status': row.get('status') or 'received', 'created_at': row['submitted_at'],
            'latitude': coordinates[0], 'longitude': coordinates[1],
            'photo_ids': [str(UUID(path.rsplit('/', 1)[-1])) for path in paths],
            'delivery_status': 'delivered'}


def snapshot():
    """Short cache bounds API usage; fetch every page, never silently truncate."""
    global _snapshot, _snapshot_time
    with _snapshot_lock:
        if _snapshot is not None and time.monotonic() - _snapshot_time < 1:
            return _snapshot
        first = request('GET', '/tables/public_reports?page=1')
        total, page_size = int(first['total']), int(first['pageSize'])
        if total > 2000 or page_size <= 0:
            raise DBStudiosError('The demo inbox supports up to 2,000 reports. Open DBStudios to review the full table.')
        rows = list(first['rows'])
        for page in range(2, (total + page_size - 1) // page_size + 1):
            rows.extend(request('GET', f'/tables/public_reports?page={page}')['rows'])
        try:
            reports = [decode(row) for row in rows]
        except (ValueError, KeyError, TypeError, IndexError):
            raise DBStudiosError('A DBStudios report row has invalid fields. Check the public_reports table.') from None
        _snapshot = sorted(reports, key=lambda report: (report['created_at'], report['id']), reverse=True)
        _snapshot_time = time.monotonic()
        return _snapshot
