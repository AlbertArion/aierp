from fastapi import FastAPI

# 说明：集中注册各业务模块的路由

def register_routes(app: FastAPI) -> None:
    from .v1 import data, predict, process, orders, auth, work_reports, pricing, batch_pricing, sap_work_reports, sd_agent, pp_agent, mm_agent, business_issues, operation_evaluation, metric_config

    app.include_router(data.router, prefix="/api/data", tags=["data"])
    app.include_router(predict.router, prefix="/api/predict", tags=["predict"])
    app.include_router(process.router, prefix="/api/process", tags=["process"])
    app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(work_reports.router, prefix="/api", tags=["work_reports"])
    app.include_router(pricing.router, prefix="/api/pricing", tags=["pricing"])
    app.include_router(batch_pricing.router, prefix="/api", tags=["pricing_batch"])
    app.include_router(sap_work_reports.router, tags=["sap_work_reports"])
    app.include_router(sd_agent.router, prefix="/api", tags=["sd_agent"])
    app.include_router(pp_agent.router, prefix="/api", tags=["pp_agent"])
    app.include_router(mm_agent.router, prefix="/api", tags=["mm_agent"])
    app.include_router(business_issues.router, prefix="/api", tags=["业务问题"])
    app.include_router(operation_evaluation.router, prefix="/api", tags=["操作评估"])
    app.include_router(metric_config.router, prefix="/api", tags=["指标配置"])


