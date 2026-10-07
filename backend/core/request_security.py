"""Bound untrusted HTTP bodies before JSON parsing and validate the Host."""
from urllib.parse import urlsplit
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from backend.core.config import settings

MAX_REQUEST_BYTES = 2 * 1024 * 1024


class RequestSecurityMiddleware:
    def __init__(self, app):
        self.app = app
        # Browser origin hosts are the canonical deployment hosts. Loopback is
        # reserved for internal readiness probes; testserver is never production.
        self.hosts = {urlsplit(origin).hostname for origin in settings.allowed_origins}
        self.hosts.update({"127.0.0.1", "localhost", "[::1]"})
        if settings.ENVIRONMENT != "production":
            self.hosts.add("testserver")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        hosts = headers.getlist("host")
        host = ""
        if len(hosts) == 1:
            try:
                authority = urlsplit("//" + hosts[0])
                port = authority.port
                if (authority.netloc == hosts[0] and not authority.username and not authority.password
                        and not any(c.isspace() for c in hosts[0])
                        and (port is None or 1 <= port <= 65535)):
                    host = authority.hostname
            except ValueError:
                pass
        if host not in self.hosts:
            return await JSONResponse({"detail": "Invalid host."}, 400)(scope, receive, send)
        lengths = headers.getlist("content-length")
        if lengths:
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                return await JSONResponse({"detail": "Invalid content length."}, 400)(scope, receive, send)
            if len(lengths[0]) > 10 or int(lengths[0]) > MAX_REQUEST_BYTES:
                return await JSONResponse({"detail": "Request body exceeds the 2 MB limit."}, 413)(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                return await JSONResponse({"detail": "Request body exceeds the 2 MB limit."}, 413)(scope, receive, send)
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
