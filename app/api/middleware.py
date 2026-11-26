"""Observe HTTP requests without reading bodies, credentials, or query strings."""

import logging
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        identifier = uuid4().hex
        scope.setdefault("state", {})["request_id"] = identifier
        context = request_id.set(identifier)
        started = perf_counter()
        status_code = 500

        async def send_response(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = identifier
            await send(message)

        def fields() -> dict:
            route = scope.get("route")
            return {
                "method": scope["method"],
                "route": getattr(route, "path", "<unmatched>"),
                "status_code": status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            }

        try:
            await self.app(scope, receive, send_response)
        except Exception:
            logger.error("request_failed", extra=fields(), exc_info=True)
            raise
        else:
            level = logging.ERROR if status_code >= 500 else (
                logging.WARNING if status_code >= 400 else logging.INFO
            )
            logger.log(level, "request_completed", extra=fields())
        finally:
            request_id.reset(context)
