"""Public reporting workflow, upload boundaries, retries and browser isolation."""
import io
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import delete

from backend.main import app
from backend.database import Session
from backend.public_reports.models import PublicReport, ReportPhoto, ReportDelivery
from backend.public_reports.storage import initialise_reports
from backend.public_reports.router import MAX_PHOTO_BYTES, MAX_REQUEST_BYTES

KEY_A = 'browser-a-' + 'a' * 64
KEY_B = 'browser-b-' + 'b' * 64


@pytest.fixture
def client():
    initialise_reports()
    with Session.begin() as session:
        session.execute(delete(ReportDelivery))
        session.execute(delete(ReportPhoto))
        session.execute(delete(PublicReport))
    with TestClient(app) as client:
        yield client


def payload(**changes):
    return {'request_id': str(uuid4()), 'category': 'facilities',
            'location': 'City Hall, Exit B', 'description': 'The light beside the lift is flickering.',
            **changes}


def image_bytes():
    output = io.BytesIO()
    image = Image.new('RGB', (120, 80), '#34765d')
    exif = Image.Exif()
    exif[270] = 'Metadata that must not be retained'
    image.save(output, format='JPEG', exif=exif)
    return output.getvalue()


def submit(client, data=None, key=KEY_A, photos=None):
    return client.post('/api/public/reports', headers={'X-Report-Key': key},
                       data={'report': json.dumps(data or payload())},
                       files=photos)


def test_round_trip_with_photo_and_private_ownership(client):
    response = submit(client, photos=[('photos', ('test.jpg', image_bytes(), 'image/jpeg'))])
    assert response.status_code == 201, response.text
    report = response.json()
    assert report['status'] == 'received'
    assert report['reference'].startswith('PLZ-')
    assert report['created_at'].endswith('+00:00')
    assert 'owner_hash' not in report
    reports = client.get('/api/public/reports', headers={'X-Report-Key': KEY_A}).json()['reports']
    assert reports == [report]
    assert client.get('/api/public/reports', headers={'X-Report-Key': KEY_B}).json()['reports'] == []
    path = f"/api/public/reports/{report['id']}/photos/{report['photo_ids'][0]}"
    assert client.get(path, headers={'X-Report-Key': KEY_B}).status_code == 404
    photo = client.get(path, headers={'X-Report-Key': KEY_A})
    assert photo.status_code == 200
    assert photo.headers['content-type'] == 'image/jpeg'
    assert photo.headers['cache-control'] == 'no-store'
    with Image.open(io.BytesIO(photo.content)) as image:
        assert not image.getexif()


def test_optional_photos_and_idempotent_retry(client):
    data = payload(latitude=1.3, longitude=103.8)
    first = submit(client, data)
    retry = submit(client, data)
    assert first.status_code == retry.status_code == 201
    assert first.json() == retry.json()
    assert first.json()['photo_ids'] == []
    assert len(client.get('/api/public/reports', headers={'X-Report-Key': KEY_A}).json()['reports']) == 1
    assert submit(client, {**data, 'description': 'An edited report with the same request id.'}).status_code == 409
    assert submit(client, data, key=KEY_B).status_code == 409


@pytest.mark.parametrize('changes', [
    {'category': 'unknown'}, {'location': '   '}, {'description': '         '},
    {'description': 'x' * 2001}, {'latitude': 200, 'longitude': 103},
    {'latitude': 1.3}, {'longitude': float('nan'), 'latitude': 1.3},
])
def test_invalid_details_rejected(client, changes):
    assert submit(client, payload(**changes)).status_code == 422


def test_invalid_and_oversized_uploads_rejected(client):
    assert submit(client, photos=[('photos', ('evil.jpg', b'<script>alert(1)</script>', 'image/jpeg'))]).status_code == 422
    assert submit(client, photos=[('photos', ('big.jpg', b'x' * (MAX_PHOTO_BYTES + 1), 'image/jpeg'))]).status_code == 413
    assert submit(client, photos=[('photos', ('small.jpg', image_bytes(), 'image/jpeg'))] * 4).status_code == 400
    assert client.post('/api/public/reports', headers={'X-Report-Key': KEY_A}, content=b'x' * (MAX_REQUEST_BYTES + 1)).status_code == 413
    assert client.get('/api/public/reports', headers={'X-Report-Key': KEY_A}).json()['reports'] == []


def test_requires_browser_key_and_checks_origin(client):
    assert client.get('/api/public/reports').status_code == 422
    assert client.get('/api/public/reports', headers={'X-Report-Key': 'short'}).status_code == 422
    response = client.post('/api/public/reports', headers={'X-Report-Key': KEY_A, 'Origin': 'https://unrelated.example'},
                           data={'report': json.dumps(payload())})
    assert response.status_code == 403


def test_daily_demo_limit(client):
    for _ in range(20):
        assert submit(client).status_code == 201
    assert submit(client).status_code == 429
    assert submit(client, key=KEY_B).status_code == 201


def test_public_entry_does_not_replace_workspace(client):
    assert client.get('/api/health').json()['ok'] is True
    # CI builds the frontend before running tests; permit source-only checkouts.
    from backend.main import dist
    if (dist / 'index.html').exists():
        assert client.get('/public/').status_code == 200
        assert client.get('/public').status_code == 200


def mock_dbstudios(monkeypatch):
    from backend.public_reports import dbstudios
    rows = []
    monkeypatch.setenv('DBSTUDIOS_API_URL', 'https://dbstudios.test/api/v1/projects/test')
    monkeypatch.setenv('DBSTUDIOS_API_KEY', 'test-only-api-key')
    dbstudios.invalidate()

    def request(method, path, body=None):
        if path == '/query':
            report_id = body['sql'].split("'")[1]
            return {'rows': [row for row in rows if row['report_id'] == report_id]}
        if method == 'POST':
            rows.append({'id': len(rows) + 1, **body['values']})
            return {'id': len(rows)}
        page = int(path.rsplit('=', 1)[1])
        return {'rows': rows[(page - 1) * 50:page * 50], 'total': len(rows), 'pageSize': 50}

    monkeypatch.setattr(dbstudios, 'request', request)
    return rows


def test_db_studios_delivery_preserves_full_text_and_coordinates(client, monkeypatch):
    from backend.public_reports import dbstudios
    rows = mock_dbstudios(monkeypatch)
    data = payload(description='Detail with emoji 🚆 and café. ' * 60, latitude=1.305678, longitude=103.856789)
    response = submit(client, data, photos=[('photos', ('test.jpg', image_bytes(), 'image/jpeg'))])
    assert response.status_code == 201, response.text
    report = response.json()
    assert report['delivery_status'] == 'delivered'
    assert len(rows) == 1
    decoded = dbstudios.decode(rows[0])
    assert decoded['description'] == data['description'].strip()
    assert decoded['latitude'] == data['latitude']
    assert decoded['photo_ids'] == report['photo_ids']
    assert max(len(rows[0][key]) for key in ('description', 'description_2', 'description_3', 'description_4')) <= 500
    # The operator view reads DBStudios, including changes made there.
    rows[0]['status'] = 'in_review'
    inbox = client.get('/api/operator/reports').json()
    assert inbox['storage']['destination'] == 'dbstudios'
    assert inbox['reports'][0]['status'] == 'in_review'
    assert inbox['reports'][0]['description'] == decoded['description']
    assert 'owner_hash' not in inbox['reports'][0]


def test_db_studios_outage_queues_and_retry_does_not_duplicate(client, monkeypatch):
    from backend.public_reports import dbstudios
    from backend.public_reports.delivery import retry_pending
    rows = mock_dbstudios(monkeypatch)
    healthy_request = dbstudios.request
    def unavailable(*args, **kwargs):
        raise dbstudios.DBStudiosError('Offline')
    monkeypatch.setattr(dbstudios, 'request', unavailable)
    data = payload()
    response = submit(client, data)
    assert response.status_code == 202
    assert response.json()['delivery_status'] == 'pending'
    assert client.get('/api/public/reports', headers={'X-Report-Key': KEY_A}).json()['reports'][0]['delivery_status'] == 'pending'
    assert client.get('/api/operator/reports').status_code == 503  # No fake local fallback.
    monkeypatch.setattr(dbstudios, 'request', healthy_request)
    retry_pending()
    retry_pending()
    assert len(rows) == 1
    assert submit(client, data).json()['delivery_status'] == 'delivered'
    assert len(rows) == 1


def test_db_studios_timeout_after_insert_is_idempotent(client, monkeypatch):
    from backend.public_reports import dbstudios
    from backend.public_reports.delivery import retry_pending
    rows = mock_dbstudios(monkeypatch)
    healthy_request = dbstudios.request
    def lost_response(method, path, body=None):
        result = healthy_request(method, path, body)
        if path.endswith('/rows'):
            raise dbstudios.DBStudiosError('Reply lost after saving')
        return result
    monkeypatch.setattr(dbstudios, 'request', lost_response)
    assert submit(client).status_code == 202
    assert len(rows) == 1
    monkeypatch.setattr(dbstudios, 'request', healthy_request)
    retry_pending()
    assert len(rows) == 1


@pytest.mark.parametrize('cloud_storage', [False, True])
def test_public_demo_opens_inbox_and_photos_without_login(client, monkeypatch, cloud_storage):
    if cloud_storage:
        mock_dbstudios(monkeypatch)
    monkeypatch.setenv('PLIZ_ENV', 'production')
    monkeypatch.setattr(app.state.security, 'production', True)
    monkeypatch.setattr(app.state.security, 'public_demo', True)
    monkeypatch.setattr(app.state.security, 'username', '')
    monkeypatch.setattr(app.state.security, 'password', '')
    report = submit(client, photos=[('photos', ('test.jpg', image_bytes(), 'image/jpeg'))]).json()
    inbox = client.get('/api/operator/reports')
    assert inbox.status_code == 200
    assert inbox.json()['reports'][0]['reference'] == report['reference']
    assert inbox.headers['cache-control'] == 'no-store'
    if cloud_storage:
        assert inbox.json()['storage']['destination'] == 'dbstudios'
    photo = client.get(f"/api/operator/reports/{report['id']}/photos/{report['photo_ids'][0]}")
    assert photo.status_code == 200
    assert photo.headers['content-type'] == 'image/jpeg'
    assert photo.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('public_readonly', [False, True])
def test_private_production_inbox_and_photos_require_login(client, monkeypatch, public_readonly):
    report = submit(client, photos=[('photos', ('test.jpg', image_bytes(), 'image/jpeg'))]).json()
    monkeypatch.setenv('PLIZ_ENV', 'production')
    monkeypatch.setattr(app.state.security, 'production', True)
    monkeypatch.setattr(app.state.security, 'public_demo', False)
    monkeypatch.setattr(app.state.security, 'public_readonly', public_readonly)
    monkeypatch.setattr(app.state.security, 'username', 'operator')
    monkeypatch.setattr(app.state.security, 'password', 'test-only-operator-password')
    photo_path = f"/api/operator/reports/{report['id']}/photos/{report['photo_ids'][0]}"
    assert client.get('/api/operator/reports').status_code == 401
    assert client.get(photo_path).status_code == 401
    assert client.get('/api/operator/reports', auth=('operator', 'wrong')).status_code == 401
    assert client.get('/api/operator/reports', auth=('operator', 'test-only-operator-password')).status_code == 200
    assert client.get(photo_path, auth=('operator', 'test-only-operator-password')).status_code == 200
    # Let read requests reach the endpoint's own configuration check.
    monkeypatch.setattr(app.state.security, 'public_readonly', True)
    monkeypatch.setattr(app.state.security, 'password', '')
    assert client.get('/api/operator/reports').status_code == 503


def test_inbox_search_and_category_filters(client):
    submit(client, payload(location='City Hall, Exit B', category='facilities'))
    submit(client, payload(location='Demo station, Platform 2', category='cleanliness'), key=KEY_B)
    inbox = client.get('/api/operator/reports?q=exit&category=facilities').json()
    assert inbox['total'] == 1
    assert inbox['reports'][0]['location'] == 'City Hall, Exit B'
    assert inbox['summary']['total'] == 2
    assert client.get('/api/operator/reports?q=%25').json()['total'] == 0


def test_db_studios_inbox_searches_later_cloud_pages(client, monkeypatch):
    from backend.public_reports import dbstudios
    rows = mock_dbstudios(monkeypatch)
    report = submit(client).json()
    template = rows[0]
    for index in range(1, 56):
        rows.append({**template, 'report_id': str(uuid4()),
                     'reference': f'PLZ-PAGE-{index:03}', 'location': f'Fictional station {index}'})
    dbstudios.invalidate()
    result = client.get('/api/operator/reports?q=PLZ-PAGE-055').json()
    assert result['total'] == 1
    assert result['reports'][0]['reference'] == 'PLZ-PAGE-055'
    assert result['summary']['total'] == 56
    second_page = client.get('/api/operator/reports?page=2').json()
    assert second_page['total'] == 56
    assert len(second_page['reports']) == 20
    assert report['delivery_status'] == 'delivered'


def test_db_studios_inbox_limit_is_explicit(client, monkeypatch):
    from backend.public_reports import dbstudios
    mock_dbstudios(monkeypatch)
    monkeypatch.setattr(dbstudios, 'request', lambda *args, **kwargs: {'total': 2001, 'pageSize': 50, 'rows': []})
    result = client.get('/api/operator/reports')
    assert result.status_code == 503
    assert '2,000' in result.json()['detail']
