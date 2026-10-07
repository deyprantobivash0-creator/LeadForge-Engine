"""Outer ASGI request correlation, including handled and unhandled error responses."""
import re
from uuid import uuid4
from backend.core.logger import request_id_context

VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class RequestIDMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        candidates = [value.decode("latin-1") for name, value in scope["headers"] if name.lower() == b"x-request-id"]
        incoming = candidates[0] if len(candidates) == 1 else ""
        correlation = incoming if VALID_REQUEST_ID.fullmatch(incoming) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = correlation
        token = request_id_context.set(correlation)
        async def correlated_send(message):
            if message["type"] == "http.response.start":
                headers = [(key, value) for key, value in message["headers"] if key.lower() != b"x-request-id"]
                message["headers"] = headers + [(b"x-request-id", correlation.encode("ascii"))]
            await send(message)
        try:
            await self.app(scope, receive, correlated_send)
        finally:
            request_id_context.reset(token)
