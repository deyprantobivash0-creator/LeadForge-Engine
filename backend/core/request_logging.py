"""One request completion event after response streaming, without payloads/queries."""
import logging
from time import perf_counter
from backend.core.config import settings
from backend.core.logger import event


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = perf_counter(); status = 500; failed = False
        async def capture(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)
        try:
            await self.app(scope, receive, capture)
        except Exception:
            failed = True
            raise
        finally:
            duration = round((perf_counter()-started)*1000, 2)
            route = scope.get("route")
            path = getattr(route, "path", "<unmatched>")
            level = logging.ERROR if failed or status >= 500 else logging.WARNING if status >= 400 else logging.DEBUG if path in {"/health", "/ready"} else logging.INFO
            fields = dict(method=scope["method"], path=path, status_code=status, duration_ms=duration)
            event("http.request.failed" if failed or status >= 500 else "http.request.completed", level=level, **fields)
            if duration >= settings.SLOW_REQUEST_MS:
                event("http.request.slow", level=logging.WARNING, **fields)
