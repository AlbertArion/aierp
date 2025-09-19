from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .middleware.request_id import RequestIdMiddleware
from .middleware.rate_limit import SimpleRateLimit

# 说明：FastAPI应用入口，注册路由与中间件

def create_app() -> FastAPI:
    app = FastAPI(title="AI ERP Backend", version="0.1.0")

    # CORS配置：前后端分离，允许本地开发端口访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 请求ID与开发环境全局限流（可按需调整limit）
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SimpleRateLimit, limit_per_minute=120)

    # 路由注册
    from .api.routes import register_routes
    register_routes(app)

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()


