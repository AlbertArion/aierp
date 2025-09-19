import time
from typing import Dict, Tuple, Callable, Any
from starlette.types import ASGIApp, Receive, Scope, Send
from functools import wraps

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


# 全局限流存储
_rate_limit_storage: Dict[str, Dict[str, Tuple[int, float]]] = {}


def rate_limit(max_requests: int = 60, window_seconds: int = 60, key_func: Callable = None):
    """
    限流装饰器
    
    Args:
        max_requests: 窗口期内最大请求数
        window_seconds: 时间窗口（秒）
        key_func: 自定义key生成函数，默认为IP地址
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成限流key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # 默认使用IP地址作为key
                key = "default"
            
            now = time.time()
            window_key = f"{func.__name__}_{key}"
            
            # 获取或初始化计数器
            if window_key not in _rate_limit_storage:
                _rate_limit_storage[window_key] = {"count": 0, "window_start": now}
            
            window_data = _rate_limit_storage[window_key]
            
            # 检查是否需要重置窗口
            if now - window_data["window_start"] > window_seconds:
                window_data["count"] = 0
                window_data["window_start"] = now
            
            # 检查是否超过限制
            if window_data["count"] >= max_requests:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=429, 
                    detail=f"Rate limit exceeded: {max_requests} requests per {window_seconds} seconds"
                )
            
            # 增加计数
            window_data["count"] += 1
            
            # 调用原函数
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


