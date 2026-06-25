"""
HTTP Basic Auth middleware — protects the whole app (API + static UI) behind
a single shared username/password. No-op unless both BASIC_AUTH_USER and
BASIC_AUTH_PASSWORD are set, so local/dev/CI usage is unaffected.
"""

from __future__ import annotations

import base64
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ola.config import BASIC_AUTH_PASSWORD, BASIC_AUTH_USER


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not (BASIC_AUTH_USER and BASIC_AUTH_PASSWORD) or request.method == "OPTIONS":
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header[6:]).decode("utf-8")
                user, _, password = decoded.partition(":")
            except Exception:
                user, password = "", ""
            if secrets.compare_digest(user, BASIC_AUTH_USER) and secrets.compare_digest(
                password, BASIC_AUTH_PASSWORD
            ):
                return await call_next(request)

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="OLA"'},
        )
