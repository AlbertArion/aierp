#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
库存成本分析API接口
提供库存成本指标查询、根因分析、执行处置方案、趋势数据等能力
优先从真实 ERP 数据源获取，失败时降级到 mock 数据
"""

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import logging
import time
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory-cost", tags=["库存成本分析"])


# ========== TTL 内存缓存 ==========

class _TTLCache:
    """简易 TTL 缓存，避免指标/根因数据短时间内重复拉取与计算"""
    def __init__(self, ttl_seconds: int = 300):
        self._store: Dict[str, Any] = {}  # key -> (value, expire_ts)
        self._ttl = ttl_seconds

    def get(self, key: str):
        entry = self._store.get(key)
        if entry and entry[1] > time.time():
            return entry[0]
        # 过期或不存在
        self._store.pop(key, None)
        return None

    def set(self, key: str, value):
        self._store[key] = (value, time.time() + self._ttl)

    def invalidate(self, key: str = None):
        if key:
            self._store.pop(key, None)
        else:
            self._store.clear()


# 指标缓存 5 分钟，根因缓存 5 分钟
_metrics_cache = _TTLCache(ttl_seconds=300)
_root_cause_cache = _TTLCache(ttl_seconds=300)


# ========== 请求/响应模型 ==========

class ExecuteActionRequest(BaseModel):
    """执行根因处置操作请求"""
    root_cause_id: str
    action_id: str
    action_type: str
    goal_type: str = "inventory_cost"


class RootCauseAction(BaseModel):
    """推荐操作"""
    id: str
    description: str
    status: str = "pending"
    action_type: str


class RelatedMaterial(BaseModel):
    """相关物料"""
    code: str
    name: str


class RootCause(BaseModel):
    """根因"""
    id: str
    title: str
    description: str
    impact_level: str  # critical, warning, info
    impact_value: float
    impact_unit: str = "万元"
    related_materials: List[RelatedMaterial] = []
    recommended_actions: List[RootCauseAction] = []


class RootCauseAnalysisResponse(BaseModel):
    """根因分析响应"""
    goal_type: str
    analysis_time: str
    root_causes: List[RootCause]


class ExecuteActionResponse(BaseModel):
    """执行操作响应"""
    success: bool
    action_id: str
    action_type: str
    message: str
    predicted_impact: Dict[str, Any] = {}


class TrendDataPoint(BaseModel):
    """趋势数据点"""
    date: str
    value: float


class TrendResponse(BaseModel):
    """趋势数据响应"""
    metric_code: str
    metric_name: str
    unit: str
    data_points: List[TrendDataPoint]


class BusinessIntelligenceChatRequest(BaseModel):
    """业务智能聊天请求：目标、现状、问题 + 用户问题，由大模型给出解决方案"""
    query: str
    metrics: Optional[List[dict]] = None  # 可选，不传则后端拉取
    root_causes: Optional[List[dict]] = None  # 可选，不传则后端拉取


# ========== 辅助函数：从请求头提取认证信息 ==========

def _extract_auth(request: Request) -> dict:
    """从 FastAPI Request 中提取 token / mandt / tenant_id"""
    token = request.headers.get("Blade-Auth") or request.headers.get("Authorization")
    mandt = request.headers.get("X-Mandt")
    tenant_id = request.headers.get("X-Tenant-Id") or mandt
    return {"token": token, "mandt": mandt, "tenant_id": tenant_id}


def _get_service(request: Request):
    """创建 InventoryCostService 实例"""
    from ...services.inventory_cost_service import InventoryCostService
    auth = _extract_auth(request)
    return InventoryCostService(**auth)


# ========== Mock 数据（降级用） ==========

def get_mock_metrics() -> List[dict]:
    """返回模拟的 7 个指标数据"""
    return [
        {"id": "ending_inventory_value", "metric_code": "ENDING_INVENTORY_VALUE", "metric_name": "期末库存金额", "unit": "万元", "current_value": 2850, "target_value": 2400, "severity": "critical", "deviation": 450, "data_source": "mock"},
        {"id": "inventory_turnover", "metric_code": "INVENTORY_TURNOVER", "metric_name": "库存周转率", "unit": "次/年", "current_value": 3.5, "target_value": 4.0, "severity": "warning", "deviation": -0.5, "data_source": "mock"},
        {"id": "sales_inventory_ratio", "metric_code": "SALES_INVENTORY_RATIO", "metric_name": "销存比", "unit": "%", "current_value": 72.3, "target_value": 85, "severity": "warning", "deviation": -12.7, "data_source": "mock"},
        {"id": "dsi", "metric_code": "DSI", "metric_name": "DSI (库存天数)", "unit": "天", "current_value": 105, "target_value": 90, "severity": "critical", "deviation": 15, "data_source": "mock"},
        {"id": "obsolete_inventory_ratio", "metric_code": "OBSOLETE_INVENTORY_RATIO", "metric_name": "呆滞库存占比", "unit": "%", "current_value": 18.5, "target_value": 10, "severity": "critical", "deviation": 8.5, "data_source": "mock"},
        {"id": "shortage_rate", "metric_code": "SHORTAGE_RATE", "metric_name": "缺料率", "unit": "%", "current_value": 5.2, "target_value": 3, "severity": "warning", "deviation": 2.2, "data_source": "mock"},
        {"id": "forecast_accuracy", "metric_code": "FORECAST_ACCURACY", "metric_name": "需求预测准确率", "unit": "%", "current_value": 75, "target_value": 85, "severity": "warning", "deviation": -10, "data_source": "mock"},
    ]


def get_mock_root_causes() -> List[dict]:
    """返回模拟的库存成本根因数据"""
    return [
        {
            "id": "rc_obsolete",
            "title": "呆滞库存积压",
            "description": "超过180天未动的库存占比达 18.5%，金额约 527万元",
            "impact_level": "critical",
            "impact_value": 527,
            "impact_unit": "万元",
            "related_materials": [
                {"code": "MAT-10023", "name": "铜套组件A"},
                {"code": "MAT-10045", "name": "密封垫圈B型"},
                {"code": "MAT-10078", "name": "轴承座C-200"},
                {"code": "MAT-10091", "name": "法兰盘D型"},
                {"code": "MAT-10102", "name": "弹簧片E-50"},
                {"code": "MAT-10115", "name": "齿轮组F型"},
            ],
            "recommended_actions": [
                {"id": "act_dispose", "description": "生成呆滞物料处置方案（报废/折价/转移）", "status": "pending", "action_type": "generate_disposal_plan"},
                {"id": "act_promo", "description": "针对可用呆滞物料创建促销清仓计划", "status": "pending", "action_type": "create_clearance_plan"},
            ],
        },
        {
            "id": "rc_forecast",
            "title": "需求预测偏差大",
            "description": "近3月预测准确率仅 75%，导致多余采购约 320万元",
            "impact_level": "warning",
            "impact_value": 320,
            "impact_unit": "万元",
            "related_materials": [
                {"code": "MAT-20015", "name": "电机线圈组"},
                {"code": "MAT-20033", "name": "控制板PCB"},
                {"code": "MAT-20048", "name": "传感器模组"},
            ],
            "recommended_actions": [
                {"id": "act_forecast", "description": "优化预测模型，引入ML算法提升准确率", "status": "pending", "action_type": "optimize_forecast"},
                {"id": "act_review", "description": "发起S&OP预测校准会议", "status": "pending", "action_type": "schedule_sop_review"},
            ],
        },
        {
            "id": "rc_safety_stock",
            "title": "安全库存设置偏高",
            "description": "42个物料安全库存覆盖天数超30天，多占资金约 185万元",
            "impact_level": "warning",
            "impact_value": 185,
            "impact_unit": "万元",
            "related_materials": [
                {"code": "MAT-30012", "name": "标准螺栓M10"},
                {"code": "MAT-30028", "name": "减速器壳体"},
                {"code": "MAT-30041", "name": "液压油管"},
                {"code": "MAT-30055", "name": "过滤网组件"},
            ],
            "recommended_actions": [
                {"id": "act_safety", "description": "基于实际Lead Time重新计算安全库存水位", "status": "pending", "action_type": "recalculate_safety_stock"},
            ],
        },
    ]


def get_action_result(action_type: str) -> dict:
    """根据操作类型返回模拟执行结果"""
    results = {
        "generate_disposal_plan": {
            "message": "已生成呆滞物料处置方案，涉及6项物料，预计释放资金158万元",
            "predicted_impact": {
                "ending_inventory_value": {"before": 2850, "after": 2692, "change": -158, "unit": "万元"},
                "obsolete_inventory_ratio": {"before": 18.5, "after": 13.2, "change": -5.3, "unit": "%"},
                "dsi": {"before": 105, "after": 95, "change": -10, "unit": "天"},
            },
        },
        "create_clearance_plan": {
            "message": "已创建促销清仓计划，针对3项可用呆滞物料，预计消化库存192万元",
            "predicted_impact": {
                "ending_inventory_value": {"before": 2850, "after": 2658, "change": -192, "unit": "万元"},
                "obsolete_inventory_ratio": {"before": 18.5, "after": 11.8, "change": -6.7, "unit": "%"},
            },
        },
        "optimize_forecast": {
            "message": "预测模型优化方案已生成，预计准确率从75%提升至83%",
            "predicted_impact": {
                "forecast_accuracy": {"before": 75, "after": 83, "change": 8, "unit": "%"},
                "ending_inventory_value": {"before": 2850, "after": 2650, "change": -200, "unit": "万元"},
            },
        },
        "schedule_sop_review": {
            "message": "已创建S&OP预测校准会议，已发送会议邀请",
            "predicted_impact": {},
        },
        "recalculate_safety_stock": {
            "message": "安全库存重新计算完成，38个物料下调（平均下调35%），预计释放资金185万元",
            "predicted_impact": {
                "ending_inventory_value": {"before": 2850, "after": 2665, "change": -185, "unit": "万元"},
                "dsi": {"before": 105, "after": 97, "change": -8, "unit": "天"},
            },
        },
    }
    return results.get(action_type, {
        "message": f"操作 {action_type} 已执行",
        "predicted_impact": {},
    })


# ========== API 路由 ==========

@router.get("/metrics", summary="获取库存成本 7 个指标实时值")
async def get_inventory_metrics(request: Request):
    """
    返回 7 个库存成本核心指标的实时计算值，供 BusinessIssueCard 使用。
    优先从 Java ERP 数据源计算，失败时降级到 mock 数据。
    结果缓存 5 分钟（TTL），避免短时间内重复拉取 ERP 接口。
    """
    cache_key = "metrics"
    cached = _metrics_cache.get(cache_key)
    if cached:
        logger.info("命中指标缓存，直接返回")
        return cached

    try:
        service = _get_service(request)
        metrics = await service.calculate_all_metrics()
        # 检查是否所有指标都无数据，如果是则降级
        has_data = any(m.get("current_value") is not None for m in metrics)
        if has_data:
            logger.info(f"成功获取真实库存指标数据，共 {len(metrics)} 项")
            result = {"success": True, "data": metrics, "source": "erp"}
            _metrics_cache.set(cache_key, result)
            return result
        else:
            logger.warning("所有指标均无真实数据，降级到 mock")
            result = {"success": True, "data": get_mock_metrics(), "source": "mock"}
            _metrics_cache.set(cache_key, result)
            return result
    except Exception as e:
        logger.warning(f"获取真实库存指标失败，降级到 mock: {e}")
        return {"success": True, "data": get_mock_metrics(), "source": "mock"}


@router.get("/root-cause-analysis", summary="获取库存成本根因分析")
async def get_root_cause_analysis(
    request: Request,
    goal_type: str = "inventory_cost",
):
    """
    获取库存成本根因分析结果。
    优先从真实 ERP 数据分析，失败时降级到 mock 数据。
    结果缓存 5 分钟（TTL），避免短时间内重复拉取 ERP 接口。
    """
    cache_key = f"root_cause_{goal_type}"
    cached = _root_cause_cache.get(cache_key)
    if cached:
        logger.info("命中根因分析缓存，直接返回")
        return cached

    logger.info(f"获取库存成本根因分析: goal_type={goal_type}")

    try:
        service = _get_service(request)
        root_causes = await service.analyze_root_causes()
        if root_causes:
            logger.info(f"成功获取真实根因数据，共 {len(root_causes)} 项")
            result = {
                "goal_type": goal_type,
                "analysis_time": datetime.now().isoformat(),
                "root_causes": root_causes,
                "source": "erp",
            }
            _root_cause_cache.set(cache_key, result)
            return result
    except Exception as e:
        logger.warning(f"真实根因分析失败，降级到 mock: {e}")

    # 降级到 mock
    return {
        "goal_type": goal_type,
        "analysis_time": datetime.now().isoformat(),
        "root_causes": get_mock_root_causes(),
        "source": "mock",
    }


@router.post("/execute-action", summary="执行根因处置操作")
async def execute_root_cause_action(
    request_body: ExecuteActionRequest,
):
    """
    执行根因分析推荐的处置操作。
    当前保持模拟执行（因为真实执行涉及 ERP 写操作，需人工审核）。
    """
    logger.info(
        f"执行根因处置操作: root_cause_id={request_body.root_cause_id}, "
        f"action_id={request_body.action_id}, action_type={request_body.action_type}"
    )

    result = get_action_result(request_body.action_type)

    return {
        "success": True,
        "action_id": request_body.action_id,
        "action_type": request_body.action_type,
        "message": result["message"],
        "predicted_impact": result["predicted_impact"],
    }


def _build_bi_context_text(metrics: List[dict], root_causes: List[dict]) -> str:
    """将目标、现状、问题格式化为大模型上下文"""
    lines = []
    lines.append("【一、目标指标（当前 vs 目标）】")
    for m in (metrics or []):
        name = m.get("metric_name") or m.get("metric_code") or ""
        cur = m.get("current_value")
        tgt = m.get("target_value")
        unit = m.get("unit") or ""
        dev = m.get("deviation")
        status = "⚠️ 偏离" if (dev and ( (m.get("severity") == "critical") or (m.get("severity") == "warning") )) else ""
        lines.append(f"• {name}：当前 {cur}{unit}，目标 {tgt}{unit} {status}")
    lines.append("")
    lines.append("【二、根因与问题】")
    for rc in (root_causes or []):
        title = rc.get("title") or ""
        desc = rc.get("description") or ""
        impact = rc.get("impact_value")
        impact_unit = rc.get("impact_unit") or "万元"
        actions = rc.get("recommended_actions") or []
        action_desc = "；".join([a.get("description", "") for a in actions[:3]])
        lines.append(f"• {title}：{desc}（影响约 {impact}{impact_unit}）。建议：{action_desc}")
    return "\n".join(lines)


@router.post("/chat", summary="业务智能聊天：目标/现状/问题 + 用户问题 → 大模型给出解决方案")
async def business_intelligence_chat(
    request: Request,
    body: BusinessIntelligenceChatRequest,
):
    """
    将目标、现状和问题通过提示词输入给大模型，由大模型给出解决方案，返回文本供业务智能聊天展示。
    若请求中未传或传空 metrics/root_causes，则后端自动拉取；前端传入则直接使用，避免重复拉取导致长时间 loading。
    """
    import httpx as _httpx

    logger.info("业务智能 /chat 收到请求: query=%s", (body.query or "")[:80])
    metrics = body.metrics if body.metrics else None
    root_causes = body.root_causes if body.root_causes else None
    need_metrics = metrics is None or (isinstance(metrics, list) and len(metrics) == 0)
    need_root_causes = root_causes is None or (isinstance(root_causes, list) and len(root_causes) == 0)
    if need_metrics or need_root_causes:
        try:
            service = _get_service(request)
            if need_metrics:
                logger.info("业务智能 /chat 拉取指标...")
                metrics = await service.calculate_all_metrics()
                if not any(m.get("current_value") is not None for m in metrics):
                    metrics = get_mock_metrics()
            if need_root_causes:
                logger.info("业务智能 /chat 拉取根因...")
                root_causes = await service.analyze_root_causes()
                if not root_causes:
                    root_causes = get_mock_root_causes()
        except Exception as e:
            logger.warning("拉取指标/根因失败，使用 mock: %s", e)
            if need_metrics:
                metrics = get_mock_metrics()
            if need_root_causes:
                root_causes = get_mock_root_causes()
    else:
        logger.info("业务智能 /chat 使用前端传入的 metrics/root_causes，跳过拉取")

    context_text = _build_bi_context_text(metrics, root_causes)
    user_query = (body.query or "").strip() or "请根据当前目标、现状与问题给出改进建议与可执行方案。"

    from app.services.config_service import ConfigService
    config_service = ConfigService()
    use_llm = config_service.is_llm_enabled("sd")
    if not use_llm:
        return {
            "success": False,
            "message": "LLM 未配置或未启用，请在系统设置中配置大模型",
            "data": {"text": None},
        }
    llm_config = config_service.get_llm_config("sd")
    api_key = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    model = llm_config.get("model", "qwen-max-latest")
    if not api_key or not base_url:
        return {
            "success": False,
            "message": "LLM API Key 或 Base URL 未配置",
            "data": {"text": None},
        }

    system_prompt = (
        "你是企业 ERP 业务智能助手，专注库存成本与供应链指标。请根据下面提供的「目标指标、现状与根因问题」，"
        "针对用户的问题或诉求，给出具体、可执行的解决方案（可包含步骤、建议措施、预期影响等）。"
        "回答请条理清晰，必要时使用列表或表格。\n\n"
        "目标、现状与问题：\n" + context_text
    )
    user_prompt = user_query

    try:
        logger.info("业务智能 /chat 调用大模型（异步）...")
        async with _httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2048,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        logger.info("业务智能 /chat 大模型返回成功")
        return {
            "success": True,
            "data": {"text": content.strip()},
        }
    except Exception as e:
        logger.exception("业务智能聊天 LLM 调用失败: %s", e)
        return {
            "success": False,
            "message": str(e),
            "data": {"text": None},
        }


@router.post("/chat/stream", summary="业务智能聊天（SSE 流式输出）")
async def business_intelligence_chat_stream(
    request: Request,
    body: BusinessIntelligenceChatRequest,
):
    """
    与 /chat 功能相同，但以 SSE（Server-Sent Events）流式输出大模型回复，
    前端可逐字展示，显著改善等待体验。
    事件格式：
      data: {"delta":"xxx"}        —— 增量文本
      data: {"done":true}          —— 流结束
      data: {"error":"xxx"}        —— 错误
    """
    import httpx as _httpx
    import json as _json

    logger.info("业务智能 /chat/stream 收到请求: query=%s", (body.query or "")[:80])

    # ---- 准备上下文（复用 /chat 逻辑） ----
    metrics = body.metrics if body.metrics else None
    root_causes = body.root_causes if body.root_causes else None
    need_metrics = metrics is None or (isinstance(metrics, list) and len(metrics) == 0)
    need_root_causes = root_causes is None or (isinstance(root_causes, list) and len(root_causes) == 0)

    if need_metrics or need_root_causes:
        try:
            service = _get_service(request)
            if need_metrics:
                metrics = await service.calculate_all_metrics()
                if not any(m.get("current_value") is not None for m in metrics):
                    metrics = get_mock_metrics()
            if need_root_causes:
                root_causes = await service.analyze_root_causes()
                if not root_causes:
                    root_causes = get_mock_root_causes()
        except Exception:
            if need_metrics:
                metrics = get_mock_metrics()
            if need_root_causes:
                root_causes = get_mock_root_causes()

    context_text = _build_bi_context_text(metrics, root_causes)
    user_query = (body.query or "").strip() or "请根据当前目标、现状与问题给出改进建议与可执行方案。"

    from app.services.config_service import ConfigService
    config_service = ConfigService()
    use_llm = config_service.is_llm_enabled("sd")
    if not use_llm:
        async def _err_gen():
            yield f"data: {_json.dumps({'error': 'LLM 未配置或未启用'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_err_gen(), media_type="text/event-stream")

    llm_config = config_service.get_llm_config("sd")
    api_key = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    model = llm_config.get("model", "qwen-max-latest")
    if not api_key or not base_url:
        async def _err_gen():
            yield f"data: {_json.dumps({'error': 'LLM API Key 或 Base URL 未配置'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_err_gen(), media_type="text/event-stream")

    system_prompt = (
        "你是企业 ERP 业务智能助手，专注库存成本与供应链指标。请根据下面提供的「目标指标、现状与根因问题」，"
        "针对用户的问题或诉求，给出具体、可执行的解决方案（可包含步骤、建议措施、预期影响等）。"
        "回答请条理清晰，必要时使用列表或表格。\n\n"
        "目标、现状与问题：\n" + context_text
    )

    async def _stream_generator():
        """SSE 生成器：流式读取 LLM 响应并逐块推送"""
        try:
            async with _httpx.AsyncClient(timeout=90.0) as client:
                async with client.stream(
                    "POST",
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_query},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2048,
                        "stream": True,
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        # OpenAI 兼容格式: data: {...}
                        if line.startswith("data: "):
                            payload = line[6:]
                            if payload.strip() == "[DONE]":
                                break
                            try:
                                chunk = _json.loads(payload)
                                delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content", "")
                                if delta:
                                    yield f"data: {_json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
                            except _json.JSONDecodeError:
                                continue
            # 完成信号
            yield f"data: {_json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.exception("业务智能流式聊天失败: %s", e)
            yield f"data: {_json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@router.get("/trend", summary="获取库存成本趋势数据")
async def get_inventory_cost_trend(
    request: Request,
    metric_code: str = "ENDING_INVENTORY_VALUE",
    days: int = 30,
):
    """
    获取库存成本相关指标的趋势数据。
    优先从 SQLite 快照表读取历史数据，无数据时降级到随机 mock。
    """
    logger.info(f"获取库存成本趋势: metric_code={metric_code}, days={days}")

    metric_info = {
        "ENDING_INVENTORY_VALUE": {"name": "期末库存金额", "unit": "万元", "base": 2850, "variance": 100},
        "INVENTORY_TURNOVER": {"name": "库存周转率", "unit": "次/年", "base": 3.5, "variance": 0.3},
        "DSI": {"name": "DSI (库存天数)", "unit": "天", "base": 105, "variance": 8},
        "OBSOLETE_INVENTORY_RATIO": {"name": "呆滞库存占比", "unit": "%", "base": 18.5, "variance": 2},
        "SALES_INVENTORY_RATIO": {"name": "销存比", "unit": "%", "base": 72.3, "variance": 5},
        "SHORTAGE_RATE": {"name": "缺料率", "unit": "%", "base": 5.2, "variance": 1.5},
        "FORECAST_ACCURACY": {"name": "需求预测准确率", "unit": "%", "base": 75, "variance": 5},
    }

    info = metric_info.get(metric_code, {"name": metric_code, "unit": "", "base": 100, "variance": 10})

    # 尝试从快照表读取
    try:
        service = _get_service(request)
        trend_data = service.get_trend_data(metric_code, days)
        if trend_data and len(trend_data) >= 2:
            logger.info(f"从快照表读取到 {len(trend_data)} 条趋势数据")
            return {
                "metric_code": metric_code,
                "metric_name": info["name"],
                "unit": info["unit"],
                "data_points": trend_data,
                "source": "snapshot",
            }
    except Exception as e:
        logger.warning(f"读取趋势快照失败: {e}")

    # 降级到随机 mock
    import random
    from datetime import timedelta

    data_points = []
    now = datetime.now()
    for i in range(days, 0, -1):
        date = now - timedelta(days=i)
        value = info["base"] + random.uniform(-info["variance"], info["variance"])
        data_points.append({
            "date": date.strftime("%Y-%m-%d"),
            "value": round(value, 2),
        })

    return {
        "metric_code": metric_code,
        "metric_name": info["name"],
        "unit": info["unit"],
        "data_points": data_points,
        "source": "mock",
    }
