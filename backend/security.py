"""Small shared-demo perimeter for a single-worker deployment behind HTTPS."""
from __future__ import annotations

import base64
import binascii
from collections import defaultdict, deque
import hmac
import os
import threading
import time

from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

LOCAL_ORIGINS = {
    'http://127.0.0.1:5173', 'http://localhost:5173',
    'http://127.0.0.1:8000', 'http://localhost:8000',
}


class DemoGuard:
    def __init__(self):
        self.production = os.getenv('PLIZ_ENV', 'development') == 'production'
        self.public_demo = os.getenv('PLIZ_PUBLIC_DEMO', 'false').lower() == 'true'
        self.username = os.getenv('PLIZ_AUTH_USERNAME', '')
        self.password = os.getenv('PLIZ_AUTH_PASSWORD', '')
        self.public_readonly = os.getenv('PLIZ_PUBLIC_READONLY', 'false').lower() == 'true'
        configured = {x.strip() for x in os.getenv('PLIZ_ALLOWED_ORIGINS', '').split(',') if x.strip()}
        if self.production and (not configured or (not self.public_demo and (not self.username or len(self.password) < 16))):
            raise RuntimeError('Production requires PLIZ_AUTH_USERNAME, a PLIZ_AUTH_PASSWORD of at least 16 characters, and PLIZ_ALLOWED_ORIGINS.')
        if self.production and any(not x.startswith('https://') for x in configured):
            raise RuntimeError('Production browser origins must use HTTPS.')
        self.origins = configured if self.production else LOCAL_ORIGINS | configured
        self.minute_limit = int(os.getenv('PLIZ_AI_REQUESTS_PER_MINUTE', '8'))
        self.daily_limit = int(os.getenv('PLIZ_AI_REQUESTS_PER_DAY', '200'))
        self.calls = defaultdict(deque)
        self.daily = deque()
        self.lock = threading.Lock()

    def authorised(self, header):
        try:
            kind, value = header.split(' ', 1)
            if kind.lower() != 'basic':
                return False
            user, password = base64.b64decode(value, validate=True).decode().split(':', 1)
            return hmac.compare_digest(user.encode(), self.username.encode()) & hmac.compare_digest(password.encode(), self.password.encode())
        except (ValueError, UnicodeError, binascii.Error):
            return False

    def limited(self, address):
        now = time.monotonic()
        with self.lock:
            # Bound memory even when clients change their addresses.
            for key in list(self.calls):
                queue = self.calls[key]
                while queue and queue[0] <= now - 60:
                    queue.popleft()
                if not queue:
                    del self.calls[key]
            while self.daily and self.daily[0] <= now - 86400:
                self.daily.popleft()
            queue = self.calls[address]
            if len(queue) >= self.minute_limit or len(self.daily) >= self.daily_limit:
                return True
            queue.append(now)
            self.daily.append(now)
            return False

    async def __call__(self, request, call_next):
        path = request.url.path
        read = request.method in ('GET', 'HEAD', 'OPTIONS')
        protected = not self.public_demo and (not self.public_readonly or not read or path.startswith('/api/chat/'))
        if self.production and path != '/api/health' and protected and not self.authorised(request.headers.get('authorization', '')):
            return JSONResponse({'detail': 'Sign in with the shared PLiZ demo login.'}, 401,
                                headers={'WWW-Authenticate': 'Basic realm="PLiZ", charset="UTF-8"', 'Cache-Control': 'no-store'})
        if not read and request.headers.get('origin') not in self.origins | {None}:
            return JSONResponse({'detail': 'Origin not allowed'}, 403)
        if self.production and request.method == 'POST' and path in ('/api/copilot', '/api/ai/test'):
            if self.limited(request.client.host if request.client else 'unknown'):
                return JSONResponse({'detail': 'The demo AI request limit has been reached. Try again later.'}, 429,
                                    headers={'Retry-After': '60', 'Cache-Control': 'no-store'})
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        if self.production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response


def install_security(app):
    guard = DemoGuard()
    app.middleware('http')(guard)
    if guard.production:
        from urllib.parse import urlsplit
        hosts = [urlsplit(origin).hostname for origin in guard.origins]
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts + ['localhost', '127.0.0.1'])
    return guard
