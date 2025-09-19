import time
from typing import Dict, Tuple
from starlette.types import ASGIApp, Receive, Scope, Send

# 说明：简易内存限流（令牌桶简化版），用于开发环境


class SimpleRateLimit:
    def __init__(self, app: ASGIApp, limit_per_minute: int = 60, key_header: str = "x-api-key") -> None:
        self.app = app
        self.limit = limit_per_minute
        self.key_header = key_header
        self.bucket: Dict[str, Tuple[int, float]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # 以IP或header作为限流key
        headers = dict(scope.get("headers") or [])
        key = headers.get(self.key_header.encode())
        if key is None:
            client = scope.get("client") or ("unknown", 0)
            key = f"ip:{client[0]}".encode()

        now = time.time()
        count, ts = self.bucket.get(key, (0, now))
        if now - ts > 60:
            count, ts = 0, now
        count += 1
        self.bucket[key] = (count, ts)

        if count > self.limit:
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [(b"content-type", b"application/json"), (b"retry-after", b"60")],
            })
            await send({"type": "http.response.body", "body": b'{"error":"too_many_requests"}'})
            return

        await self.app(scope, receive, send)


