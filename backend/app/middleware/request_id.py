import uuid
from typing import Callable
from starlette.types import ASGIApp, Receive, Scope, Send

# 说明：为每个请求注入 X-Request-ID，便于排查与链路追踪


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"x-request-id", request_id.encode()))
            await send(message)

        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id
        await self.app(scope, receive, send_wrapper)


