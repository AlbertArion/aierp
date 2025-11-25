"""
PP Agent AI查询接口
支持自然语言查询生产订单、报工情况、月结异常检测等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional
import re
import logging
from app.services.pp_service import PPService

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖注入：创建PPService实例，并传递token
def get_pp_service(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    blade_auth: Optional[str] = Header(None, alias="Blade-Auth")
) -> PPService:
    """创建PPService实例，并传递认证token"""
    service = PPService()
    
    # 优先从Authorization头获取token
    token = None
    if authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        else:
            token = authorization.strip()
    
    # 如果Authorization头没有token，尝试从Blade-Auth头获取
    if not token and blade_auth:
        if blade_auth.lower().startswith("bearer "):
            token = blade_auth.split(" ", 1)[1].strip()
        elif blade_auth.lower().startswith("crypto "):
            token = blade_auth.strip()
        else:
            token = blade_auth.strip()
    
    # 设置token到service
    if token:
        service.set_token(token)
        logger.info(f"Token已设置到PPService (长度: {len(token)})")
    else:
        logger.warning("未收到有效的token请求头")
    
    return service

def _extract_order_number(text: str) -> Optional[str]:
    """从文本中提取生产订单号"""
    patterns = [
        r"(?:订单号|订单|生产订单|AUFNR)[\s\-:]?([0-9]{10,})",
        r"([0-9]{10,})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            order_num = match.group(1).strip()
            if len(order_num) >= 10:
                return order_num
    
    return None

def _extract_material_number(text: str) -> Optional[str]:
    """从文本中提取物料号"""
    patterns = [
        r"(?:物料号|物料|MATNR)[\s\-:]?([A-Z0-9\-]+)",
        r"([A-Z]{1,}[0-9]{6,})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            matnr = match.group(1).strip()
            if len(matnr) >= 6:
                return matnr
    
    return None

def _identify_intent(text: str) -> str:
    """
    识别用户意图
    
    Returns:
        意图类型：NAVIGATE_*, QUERY_ORDER_*, QUERY_WORK_REPORT, QUERY_UNREPORTED_WORK,
        MONTH_END_CHECK, ADJUST_COLUMNS, SMALLTALK
    """
    text_lower = text.lower()
    
    # 字段调整意图（核心创新功能）
    if any(keyword in text_lower for keyword in ["移除", "隐藏", "不要显示", "去掉", "删除", "不显示"]):
        if any(keyword in text_lower for keyword in ["字段", "列", "单位", "类型", "工厂", "工序", "描述"]):
            return "ADJUST_COLUMNS"
    if any(keyword in text_lower for keyword in ["增加", "添加", "显示", "展示", "包含"]):
        if any(keyword in text_lower for keyword in ["字段", "列", "单位", "类型", "工厂", "工序", "描述"]):
            return "ADJUST_COLUMNS"
    if any(keyword in text_lower for keyword in ["恢复默认", "显示所有", "重置字段"]):
        return "ADJUST_COLUMNS"
    
    # 页面跳转意图
    if any(keyword in text_lower for keyword in ["跳转", "打开", "进入", "去", "导航"]):
        if "生产订单" in text_lower and "列表" in text_lower:
            return "NAVIGATE_ORDER_LIST"
        elif "生产订单" in text_lower and ("详情" in text_lower or "显示" in text_lower):
            return "NAVIGATE_ORDER_DETAIL"
        elif "报工" in text_lower:
            return "NAVIGATE_WORK_REPORT"
        elif "计划订单" in text_lower:
            return "NAVIGATE_PLANNED_ORDER"
        elif "物料需求" in text_lower or "mrp" in text_lower:
            return "NAVIGATE_MRP"
    
    # 未报工情况查询意图
    if any(keyword in text_lower for keyword in ["未报工", "待报工", "未完成报工"]):
        return "QUERY_UNREPORTED_WORK"
    
    # 报工查询意图
    if any(keyword in text_lower for keyword in ["报工", "报工情况", "报工一览表", "报工明细"]):
        return "QUERY_WORK_REPORT"
    
    # 生产订单查询意图
    if any(keyword in text_lower for keyword in ["生产订单", "订单列表", "订单查询"]):
        if "详情" in text_lower or "显示" in text_lower or _extract_order_number(text):
            return "QUERY_ORDER_DETAIL"
        else:
            return "QUERY_ORDER_LIST"
    
    # 月结异常检测意图
    if any(keyword in text_lower for keyword in ["月结", "异常检测", "检查异常", "异常数据"]):
        return "MONTH_END_CHECK"
    
    # 订单状态监控意图
    if any(keyword in text_lower for keyword in ["订单状态", "完成进度", "延迟", "进度"]):
        return "ORDER_STATUS_MONITOR"
    
    # 默认：闲聊
    return "SMALLTALK"

@router.post("/pp-agent/ai-query")
async def pp_ai_query(
    payload: Dict[str, Any],
    pp_service: PPService = Depends(get_pp_service)
) -> Dict[str, Any]:
    """
    PP模块AI查询接口
    
    支持的功能：
    1. 查询生产订单列表
    2. 查询订单详情
    3. 查询报工一览表
    4. 查询未报工情况
    5. 月结异常检测
    6. 订单状态监控
    7. 字段动态调整（核心创新功能）
    8. 页面跳转
    
    Request Body:
        {
            "query": "查询未报工情况"
        }
    
    Returns:
        {
            "success": true,
            "intent": "QUERY_UNREPORTED_WORK",
            "data": {
                "type": "work_report_list",
                "items": [...],
                "total": 100
            }
        }
    """
    try:
        query = payload.get("query", "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query不能为空")
        
        logger.info(f"收到PP Agent查询: {query}")
        
        # 识别意图
        intent = _identify_intent(query)
        logger.info(f"识别意图: {intent}")
        
        # 根据意图处理
        if intent == "QUERY_ORDER_LIST":
            # 提取查询参数
            params = {
                "current": 1,
                "size": 20  # 默认每页20条
            }
            matnr = _extract_material_number(query)
            if matnr:
                params["matnr"] = matnr
            
            result = await pp_service.get_order_list(params)
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "order_list",
                    "orders": result.get("data", {}).get("records", []),
                    "total": result.get("data", {}).get("total", 0)
                },
                "message": "查询生产订单列表成功"
            }
        
        elif intent == "QUERY_ORDER_DETAIL":
            aufnr = _extract_order_number(query)
            if not aufnr:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供生产订单号"
                }
            
            result = await pp_service.get_order_detail(aufnr)
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "order_detail",
                    "order": result.get("data", {})
                },
                "message": f"查询生产订单{aufnr}详情成功"
            }
        
        elif intent == "QUERY_UNREPORTED_WORK":
            # 提取查询参数
            params = {}
            aufnr = _extract_order_number(query)
            if aufnr:
                params["aufnr"] = aufnr
            matnr = _extract_material_number(query)
            if matnr:
                # 后端接口使用plnbez作为物料号参数
                params["plnbez"] = matnr
            
            result = await pp_service.get_unreported_work_list(params)
            
            # 检查result是否为None或不是字典
            if result is None:
                logger.warning("未报工情况查询返回None")
                return {
                    "success": False,
                    "intent": intent,
                    "message": "查询未报工情况失败：后端返回空数据",
                    "data": {
                        "type": "work_report_list",
                        "items": [],
                        "total": 0
                    }
                }
            
            # IPage对象包含records字段，需要转换为items
            page_data = result.get("data") if isinstance(result, dict) else {}
            if page_data is None:
                page_data = {}
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "work_report_list",
                    "items": page_data.get("records", []) if isinstance(page_data, dict) else [],
                    "total": page_data.get("total", 0) if isinstance(page_data, dict) else 0,
                    "column_config": page_data.get("column_config") if isinstance(page_data, dict) else None
                },
                "message": "查询未报工情况成功"
            }
        
        elif intent == "QUERY_WORK_REPORT":
            params = {}
            aufnr = _extract_order_number(query)
            if aufnr:
                params["aufnr"] = aufnr
            matnr = _extract_material_number(query)
            if matnr:
                # 后端接口使用plnbez作为物料号参数
                params["plnbez"] = matnr
            
            result = await pp_service.get_work_report_list(params)
            
            # 检查result是否为None或不是字典
            if result is None:
                logger.warning("报工一览表查询返回None")
                return {
                    "success": False,
                    "intent": intent,
                    "message": "查询报工一览表失败：后端返回空数据",
                    "data": {
                        "type": "work_report_list",
                        "items": [],
                        "total": 0
                    }
                }
            
            # IPage对象包含records字段，需要转换为items
            page_data = result.get("data") if isinstance(result, dict) else {}
            if page_data is None:
                page_data = {}
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "work_report_list",
                    "items": page_data.get("records", []) if isinstance(page_data, dict) else [],
                    "total": page_data.get("total", 0) if isinstance(page_data, dict) else 0
                },
                "message": "查询报工一览表成功"
            }
        
        elif intent == "MONTH_END_CHECK":
            result = await pp_service.month_end_check()
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "anomaly_check_result",
                    "result": result.get("data", {})
                },
                "message": "月结异常检测完成"
            }
        
        elif intent == "ORDER_STATUS_MONITOR":
            aufnr = _extract_order_number(query)
            if not aufnr:
                return {
                    "success": False,
                    "intent": intent,
                    "message": "请提供生产订单号"
                }
            
            result = await pp_service.get_order_status(aufnr)
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "status_summary",
                    "status": result.get("data", {})
                },
                "message": f"查询订单{aufnr}状态成功"
            }
        
        elif intent == "ADJUST_COLUMNS":
            # 字段调整逻辑（核心创新功能）
            # 这里返回字段调整指令，由前端处理
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "column_adjustment",
                    "action": "remove" if any(kw in query.lower() for kw in ["移除", "隐藏", "不要显示", "去掉", "删除", "不显示"]) 
                             else "add" if any(kw in query.lower() for kw in ["增加", "添加", "显示", "展示", "包含"])
                             else "reset",
                    "user_message": query
                },
                "message": "字段调整指令已识别"
            }
        
        elif intent.startswith("NAVIGATE_"):
            # 页面跳转
            route_map = {
                "NAVIGATE_ORDER_LIST": "/manufacturing/production-control",
                "NAVIGATE_ORDER_DETAIL": "/manufacturing/production-control/detail",
                "NAVIGATE_WORK_REPORT": "/manufacturing-schedule/productionReport",
                "NAVIGATE_PLANNED_ORDER": "/manufacturing/planned-order/detail",
                "NAVIGATE_MRP": "/manufacturing/material-requirement-planning"
            }
            
            route = route_map.get(intent, "/manufacturing/production-control")
            aufnr = _extract_order_number(query)
            
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "navigation",
                    "route": route,
                    "params": {"aufnr": aufnr} if aufnr else {}
                },
                "message": "正在为您跳转..."
            }
        
        else:
            # 闲聊
            return {
                "success": True,
                "intent": intent,
                "data": {
                    "type": "text",
                    "text": "我是PP Agent，可以帮助您查询生产订单、报工情况、进行月结异常检测等。请告诉我您需要什么帮助？"
                },
                "message": "PP Agent助手"
            }
    
    except Exception as e:
        logger.error(f"PP Agent查询失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

@router.post("/pp-agent/adjust-columns")
async def adjust_columns(
    payload: Dict[str, Any],
    pp_service: PPService = Depends(get_pp_service)
) -> Dict[str, Any]:
    """
    字段动态调整接口（核心创新功能）
    
    支持通过自然语言指令动态调整报表显示的字段
    
    Request Body:
        {
            "action": "remove",  # add, remove, reset
            "fields": ["gmein", "auart"],  # 字段标识列表
            "user_message": "移除订单基本单位"
        }
    
    Returns:
        {
            "success": true,
            "columns": [...],  # 更新后的字段配置
            "affected_fields": ["gmein"]
        }
    """
    try:
        action = payload.get("action", "remove")  # add, remove, reset
        fields = payload.get("fields", [])
        user_message = payload.get("user_message", "")
        
        # 字段映射表（用于识别字段别名）
        field_mappings = {
            "订单号": "aufnr", "工单号": "aufnr", "生产订单": "aufnr",
            "物料号": "plnbez", "物料编码": "plnbez", "物料编号": "plnbez",
            "物料描述": "maktx", "物料名称": "maktx", "物料文本": "maktx",
            "订单类型": "auart", "类型": "auart", "订单类型编码": "auart",
            "工厂": "werks", "工厂代码": "werks", "工厂编号": "werks",
            "工序": "vornr", "工序号": "vornr", "工序编号": "vornr",
            "工序描述": "ltxa1", "工序名称": "ltxa1", "工序文本": "ltxa1",
            "目标数量": "mgvrg", "计划数量": "mgvrg", "订单数量": "mgvrg",
            "已确认数量": "lmnga", "确认数量": "lmnga", "已报工数量": "lmnga",
            "报废数量": "xmnga", "废品数量": "xmnga", "不良品数量": "xmnga",
            "差异数量": "diff_qty", "待报工数量": "diff_qty", "未报工数量": "diff_qty",
            "基本计量单位": "gmein", "单位": "gmein", "基本单位": "gmein", "计量单位": "gmein", "订单单位": "gmein"
        }
        
        # 默认字段配置
        default_columns = [
            {"field": "aufnr", "label": "生产订单号", "visible": True},
            {"field": "plnbez", "label": "物料号", "visible": True},
            {"field": "maktx", "label": "物料描述", "visible": True},
            {"field": "auart", "label": "订单类型", "visible": True},
            {"field": "werks", "label": "工厂", "visible": True},
            {"field": "vornr", "label": "工序", "visible": True},
            {"field": "ltxa1", "label": "工序描述", "visible": True},
            {"field": "mgvrg", "label": "目标数量", "visible": True},
            {"field": "lmnga", "label": "已确认数量", "visible": True},
            {"field": "xmnga", "label": "报废数量", "visible": True},
            {"field": "diff_qty", "label": "差异数量", "visible": True},
            {"field": "gmein", "label": "基本计量单位", "visible": True}
        ]
        
        # 这里应该从请求中获取当前字段配置，或从session中获取
        # 简化实现：返回默认配置的更新版本
        current_columns = payload.get("current_columns", default_columns)
        
        if action == "reset":
            return {
                "success": True,
                "message": "已恢复默认字段配置",
                "columns": default_columns,
                "affected_fields": []
            }
        
        # 更新字段可见性
        updated_columns = current_columns.copy()
        affected_fields = []
        
        for field_identifier in fields:
            for col in updated_columns:
                if col["field"] == field_identifier:
                    col["visible"] = (action == "add")
                    affected_fields.append(field_identifier)
                    break
        
        return {
            "success": True,
            "message": f"已{'显示' if action == 'add' else '隐藏'} {len(affected_fields)} 个字段",
            "columns": updated_columns,
            "affected_fields": affected_fields
        }
    
    except Exception as e:
        logger.error(f"字段调整失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"字段调整失败: {str(e)}")

