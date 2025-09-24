from fastapi import FastAPI

# 说明：集中注册各业务模块的路由

def register_routes(app: FastAPI) -> None:
    from .v1 import data, predict, process, orders, auth, work_reports

    app.include_router(data.router, prefix="/api/data", tags=["data"])
    app.include_router(predict.router, prefix="/api/predict", tags=["predict"])
    app.include_router(process.router, prefix="/api/process", tags=["process"])
    app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(work_reports.router, prefix="/api", tags=["work_reports"])


