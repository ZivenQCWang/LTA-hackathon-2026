import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.security import DemoGuard, install_security


@pytest.fixture
def secured(monkeypatch):
    monkeypatch.setenv('PLIZ_ENV', 'production')
    monkeypatch.setenv('PLIZ_PUBLIC_DEMO', 'false')
    monkeypatch.setenv('PLIZ_AUTH_USERNAME', 'demo')
    monkeypatch.setenv('PLIZ_AUTH_PASSWORD', 'test-only-password-1234')
    monkeypatch.setenv('PLIZ_ALLOWED_ORIGINS', 'https://pliz.4bytedigi.com')
    monkeypatch.setenv('PLIZ_PUBLIC_READONLY', 'false')
    app = FastAPI()
    guard = install_security(app)
    @app.get('/api/health')
    @app.get('/api/state')
    @app.get('/api/chat/example')
    @app.post('/api/copilot')
    def endpoint():
        return {'ok': True}
    with TestClient(app, base_url='https://pliz.4bytedigi.com') as client:
        yield client, guard


AUTH = ('demo', 'test-only-password-1234')


def test_production_fails_closed(monkeypatch):
    monkeypatch.setenv('PLIZ_ENV', 'production')
    monkeypatch.setenv('PLIZ_AUTH_PASSWORD', '')
    with pytest.raises(RuntimeError, match='Production requires'):
        DemoGuard()


def test_shared_login_origin_and_host(secured):
    client, _ = secured
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/state').status_code == 401
    assert client.get('/api/state', auth=('demo', 'wrong')).status_code == 401
    assert client.get('/api/state', headers={'Authorization': 'Basic !!!!'}).status_code == 401
    response = client.get('/api/state', auth=AUTH)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/api/state', auth=AUTH, headers={'Host': 'attacker.example'}).status_code == 400
    assert client.post('/api/copilot', auth=AUTH, headers={'Origin': 'https://other.example'}).status_code == 403
    assert client.post('/api/copilot', auth=AUTH, headers={'Origin': 'https://pliz.4bytedigi.com'}).status_code == 200


def test_public_readonly_still_protects_writes_and_chat(secured):
    client, guard = secured
    guard.public_readonly = True
    assert client.get('/api/state').status_code == 200
    assert client.get('/api/chat/example').status_code == 401
    assert client.post('/api/copilot').status_code == 401


def test_ai_rate_limit(secured):
    client, guard = secured
    guard.minute_limit = 1
    assert client.post('/api/copilot', auth=AUTH).status_code == 200
    assert client.post('/api/copilot', auth=AUTH).status_code == 429
    assert client.get('/api/state', auth=AUTH).status_code == 200
    guard.calls.clear()
    guard.daily_limit = 1
    assert client.post('/api/copilot', auth=AUTH).status_code == 429


def test_explicit_public_demo_has_no_login(secured):
    client, guard = secured
    guard.public_demo = True
    assert client.get('/api/state').status_code == 200
    assert client.post('/api/copilot').status_code == 200
    assert client.post('/api/copilot', headers={'Origin': 'https://other.example'}).status_code == 403
