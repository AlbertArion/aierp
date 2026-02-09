"""
Agent操作按钮API接口
为规则模式提供操作按钮列表和执行功能
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from app.services.config_service import ConfigService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ActionExecuteRequest(BaseModel):
    action_code: str
    params: Optional[Dict[str, Any]] = None


def get_config_service():
    return ConfigService()


# 各Agent的操作按钮定义
AGENT_ACTIONS = {
    "sd": {
        "name": "SD Agent - 销售分销",
        "categories": [
            {
                "name": "订单管理",
                "icon": "Document",
                "actions": [
                    {"code": "QUERY_ORDER_LIST", "name": "查询销售订单列表", "icon": "Search", "description": "查询所有销售订单"},
                    {"code": "QUERY_ORDER_DETAIL", "name": "查看订单详情", "icon": "View", "description": "根据订单号查看详情", "need_params": True, "params_schema": [{"key": "vbeln", "label": "销售订单号", "type": "string", "required": True}]},
                    {"code": "CREATE_SALES_ORDER", "name": "创建销售订单", "icon": "Plus", "description": "创建新的销售订单"},
                ]
            },
            {
                "name": "交货管理",
                "icon": "Van",
                "actions": [
                    {"code": "QUERY_DELIVERY_LIST", "name": "查询交货单列表", "icon": "Search", "description": "查询所有交货单"},
                    {"code": "QUERY_DELIVERY_DETAIL", "name": "查看交货单详情", "icon": "View", "description": "根据交货单号查看详情", "need_params": True, "params_schema": [{"key": "delivery_vbeln", "label": "交货单号", "type": "string", "required": True}]},
                    {"code": "CREATE_DELIVERY", "name": "创建交货单", "icon": "Plus", "description": "为销售订单创建交货单", "need_params": True, "params_schema": [{"key": "vbeln", "label": "销售订单号", "type": "string", "required": True}]},
                ]
            },
            {
                "name": "开票管理",
                "icon": "Tickets",
                "actions": [
                    {"code": "QUERY_INVOICE_LIST", "name": "查询发票列表", "icon": "Search", "description": "查询所有发票"},
                    {"code": "QUERY_INVOICE_DETAIL", "name": "查看发票详情", "icon": "View", "description": "根据发票号查看详情", "need_params": True, "params_schema": [{"key": "vbeln", "label": "发票号", "type": "string", "required": True}]},
                ]
            },
            {
                "name": "综合查询",
                "icon": "DataAnalysis",
                "actions": [
                    {"code": "SALES_OVERVIEW", "name": "销售总览", "icon": "PieChart", "description": "查看销售总览数据"},
                    {"code": "ATP_CHECK", "name": "ATP检查", "icon": "CircleCheck", "description": "检查物料可用性", "need_params": True, "params_schema": [{"key": "vbeln", "label": "销售订单号", "type": "string", "required": True}]},
                ]
            }
        ]
    },
    "pp": {
        "name": "PP Agent - 生产计划",
        "categories": [
            {
                "name": "生产订单",
                "icon": "SetUp",
                "actions": [
                    {"code": "QUERY_ORDER_LIST", "name": "查询生产订单列表", "icon": "Search", "description": "查询所有生产订单"},
                    {"code": "QUERY_ORDER_DETAIL", "name": "查看订单详情", "icon": "View", "description": "根据订单号查看详情", "need_params": True, "params_schema": [{"key": "aufnr", "label": "生产订单号", "type": "string", "required": True}]},
                    {"code": "CREATE_PRODUCTION_ORDER", "name": "创建生产订单", "icon": "Plus", "description": "为销售订单创建生产订单", "need_params": True, "params_schema": [{"key": "vbeln", "label": "销售订单号", "type": "string", "required": True}]},
                    {"code": "CREATE_INTERNAL_ORDER", "name": "创建内部订单", "icon": "Plus", "description": "为销售订单创建内部订单", "need_params": True, "params_schema": [{"key": "vbeln", "label": "销售订单号", "type": "string", "required": True}]},
                ]
            },
            {
                "name": "报工管理",
                "icon": "Timer",
                "actions": [
                    {"code": "QUERY_WORK_REPORT_LIST", "name": "查询报工一览表", "icon": "List", "description": "查询报工一览表"},
                    {"code": "QUERY_UNREPORTED_WORK", "name": "查询未报工情况", "icon": "Warning", "description": "查询未报工情况"},
                ]
            },
            {
                "name": "检查与监控",
                "icon": "Monitor",
                "actions": [
                    {"code": "MONTH_END_CHECK", "name": "月结异常检测", "icon": "WarnTriangleFilled", "description": "检测月结异常情况"},
                    {"code": "ORDER_STATUS_MONITOR", "name": "订单状态监控", "icon": "Odometer", "description": "监控订单状态"},
                    {"code": "CHECK_PRODUCTION_ORDER_MATERIAL", "name": "齐套性检查", "icon": "CircleCheck", "description": "检查生产订单齐套性", "need_params": True, "params_schema": [{"key": "aufnr", "label": "生产订单号", "type": "string", "required": True}]},
                ]
            }
        ]
    },
    "mm": {
        "name": "MM Agent - 物料管理",
        "categories": [
            {
                "name": "采购订单",
                "icon": "ShoppingCart",
                "actions": [
                    {"code": "QUERY_ORDER_LIST", "name": "查询采购订单列表", "icon": "Search", "description": "查询所有采购订单"},
                    {"code": "QUERY_ORDER_DETAIL", "name": "查看订单详情", "icon": "View", "description": "根据订单号查看详情", "need_params": True, "params_schema": [{"key": "ebeln", "label": "采购订单号", "type": "string", "required": True}]},
                    {"code": "CREATE_PURCHASE_ORDER", "name": "创建采购订单", "icon": "Plus", "description": "创建新的采购订单"},
                ]
            },
            {
                "name": "采购申请",
                "icon": "Notebook",
                "actions": [
                    {"code": "QUERY_REQUISITION_LIST", "name": "查询采购申请列表", "icon": "Search", "description": "查询所有采购申请"},
                    {"code": "QUERY_REQUISITION_DETAIL", "name": "查看申请详情", "icon": "View", "description": "根据申请号查看详情", "need_params": True, "params_schema": [{"key": "banfn", "label": "采购申请号", "type": "string", "required": True}]},
                ]
            },
            {
                "name": "其他查询",
                "icon": "DataAnalysis",
                "actions": [
                    {"code": "QUERY_INFO_RECORD", "name": "查询采购信息记录", "icon": "Tickets", "description": "查询采购信息记录"},
                    {"code": "QUERY_MATERIAL_DOCUMENT", "name": "查询物料凭证", "icon": "Document", "description": "查询物料凭证"},
                ]
            }
        ]
    },
    "fi": {
        "name": "FI Agent - 财务会计",
        "categories": [
            {
                "name": "会计凭证",
                "icon": "Document",
                "actions": [
                    {"code": "QUERY_DOCUMENT_LIST", "name": "查询会计凭证列表", "icon": "Search", "description": "查询所有会计凭证"},
                    {"code": "QUERY_DOCUMENT_DETAIL", "name": "查看凭证详情", "icon": "View", "description": "根据凭证号查看详情", "need_params": True, "params_schema": [{"key": "belnr", "label": "凭证号", "type": "string", "required": True}]},
                    {"code": "CREATE_DOCUMENT", "name": "创建会计凭证", "icon": "Plus", "description": "创建新的会计凭证"},
                ]
            },
            {
                "name": "科目管理",
                "icon": "Coin",
                "actions": [
                    {"code": "QUERY_ACCOUNT_LIST", "name": "查询科目列表", "icon": "List", "description": "查询科目表"},
                    {"code": "QUERY_ACCOUNT_BALANCE", "name": "查询科目余额", "icon": "Wallet", "description": "查询科目余额", "need_params": True, "params_schema": [{"key": "saknr", "label": "科目编号", "type": "string", "required": True}]},
                ]
            },
            {
                "name": "报表查询",
                "icon": "TrendCharts",
                "actions": [
                    {"code": "QUERY_BALANCE_SHEET", "name": "资产负债表", "icon": "PieChart", "description": "查询资产负债表"},
                    {"code": "QUERY_PROFIT_LOSS", "name": "利润表", "icon": "DataLine", "description": "查询利润表"},
                    {"code": "QUERY_CASH_FLOW", "name": "现金流量表", "icon": "Money", "description": "查询现金流量表"},
                ]
            },
            {
                "name": "月结管理",
                "icon": "Calendar",
                "actions": [
                    {"code": "START_MONTH_END", "name": "启动月结", "icon": "VideoPlay", "description": "启动月结流程"},
                    {"code": "QUERY_MONTH_END_STATUS", "name": "查询月结状态", "icon": "Odometer", "description": "查询月结状态"},
                ]
            }
        ]
    },
    "co": {
        "name": "CO Agent - 成本控制",
        "categories": [
            {
                "name": "成本对象",
                "icon": "Box",
                "actions": [
                    {"code": "QUERY_COST_OBJECT_LIST", "name": "查询成本对象列表", "icon": "Search", "description": "查询所有成本对象"},
                    {"code": "QUERY_COST_OBJECT_DETAIL", "name": "查看成本对象详情", "icon": "View", "description": "根据订单号查看详情", "need_params": True, "params_schema": [{"key": "orderNumber", "label": "订单号", "type": "string", "required": True}]},
                ]
            },
            {
                "name": "内部订单",
                "icon": "Notebook",
                "actions": [
                    {"code": "QUERY_INTERNAL_ORDER_LIST", "name": "查询内部订单列表", "icon": "List", "description": "查询内部订单"},
                    {"code": "QUERY_INTERNAL_ORDER_DETAIL", "name": "查看内部订单详情", "icon": "View", "description": "查看内部订单详情", "need_params": True, "params_schema": [{"key": "orderNumber", "label": "内部订单号", "type": "string", "required": True}]},
                ]
            },
            {
                "name": "结算与月结",
                "icon": "Calendar",
                "actions": [
                    {"code": "QUERY_SETTLEMENT_RULES", "name": "结算规则查询", "icon": "Setting", "description": "查询结算规则"},
                    {"code": "CO_MONTH_END", "name": "CO月结", "icon": "VideoPlay", "description": "启动CO月结流程"},
                    {"code": "QUERY_CO_MONTH_END_STATUS", "name": "查询月结状态", "icon": "Odometer", "description": "查询CO月结状态"},
                ]
            }
        ]
    }
}


@router.get("/agent-actions/{agent_name}")
async def get_agent_actions_list(
    agent_name: str,
    config_service: ConfigService = Depends(get_config_service)
):
    """
    获取Agent可用的操作按钮列表
    
    Args:
        agent_name: Agent名称（sd, pp, mm, fi, co）
    
    Returns:
        操作按钮列表（含分类信息和LLM状态）
    """
    if agent_name not in AGENT_ACTIONS:
        raise HTTPException(status_code=404, detail=f"未找到Agent: {agent_name}")
    
    agent_config = AGENT_ACTIONS[agent_name]
    llm_enabled = config_service.is_llm_enabled(agent_name)
    
    # 扁平化所有操作列表
    all_actions = []
    for category in agent_config["categories"]:
        for action in category["actions"]:
            all_actions.append({
                **action,
                "category": category["name"]
            })
    
    return {
        "success": True,
        "data": {
            "agent_name": agent_name,
            "agent_display_name": agent_config["name"],
            "llm_enabled": llm_enabled,
            "categories": agent_config["categories"],
            "actions": all_actions
        }
    }


@router.post("/agent-actions/{agent_name}/execute")
async def execute_action(
    agent_name: str,
    request: ActionExecuteRequest,
    x_mandt: Optional[str] = Header(None, alias="X-Mandt"),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id")
):
    """
    执行操作按钮对应的功能
    
    将操作转换为对应Agent的ai-query调用格式
    """
    if agent_name not in AGENT_ACTIONS:
        raise HTTPException(status_code=404, detail=f"未找到Agent: {agent_name}")
    
    action_code = request.action_code
    params = request.params or {}
    
    # 构建查询文本（将操作码映射为自然语言查询）
    query = _build_query_from_action(agent_name, action_code, params)
    
    if not query:
        raise HTTPException(status_code=400, detail=f"不支持的操作: {action_code}")
    
    return {
        "success": True,
        "data": {
            "query": query,
            "action_code": action_code,
            "params": params,
            "agent_name": agent_name
        }
    }


def _build_query_from_action(agent_name: str, action_code: str, params: Dict[str, Any]) -> Optional[str]:
    """将操作码和参数转换为查询文本"""
    
    # SD Agent 操作映射
    sd_mappings = {
        "QUERY_ORDER_LIST": "查询销售订单列表",
        "QUERY_ORDER_DETAIL": lambda p: f"查询销售订单{p.get('vbeln', '')}的详情",
        "CREATE_SALES_ORDER": "创建销售订单",
        "QUERY_DELIVERY_LIST": "查询交货单列表",
        "QUERY_DELIVERY_DETAIL": lambda p: f"查询交货单{p.get('delivery_vbeln', '')}的详情",
        "CREATE_DELIVERY": lambda p: f"为销售订单{p.get('vbeln', '')}创建交货单",
        "QUERY_INVOICE_LIST": "查询发票列表",
        "QUERY_INVOICE_DETAIL": lambda p: f"查询发票{p.get('vbeln', '')}的详情",
        "SALES_OVERVIEW": "销售总览",
        "ATP_CHECK": lambda p: f"ATP检查订单{p.get('vbeln', '')}的物料可用性",
    }
    
    # PP Agent 操作映射
    pp_mappings = {
        "QUERY_ORDER_LIST": "查询生产订单列表",
        "QUERY_ORDER_DETAIL": lambda p: f"查询生产订单{p.get('aufnr', '')}的详情",
        "CREATE_PRODUCTION_ORDER": lambda p: f"为销售订单{p.get('vbeln', '')}创建生产订单",
        "CREATE_INTERNAL_ORDER": lambda p: f"为销售订单{p.get('vbeln', '')}创建内部订单",
        "QUERY_WORK_REPORT_LIST": "查询报工一览表",
        "QUERY_UNREPORTED_WORK": "查询未报工情况",
        "MONTH_END_CHECK": "月结异常检测",
        "ORDER_STATUS_MONITOR": "查询订单状态",
        "CHECK_PRODUCTION_ORDER_MATERIAL": lambda p: f"检查生产订单{p.get('aufnr', '')}的齐套性",
    }
    
    # MM Agent 操作映射
    mm_mappings = {
        "QUERY_ORDER_LIST": "查询采购订单列表",
        "QUERY_ORDER_DETAIL": lambda p: f"查询采购订单{p.get('ebeln', '')}的详情",
        "CREATE_PURCHASE_ORDER": "创建采购订单",
        "QUERY_REQUISITION_LIST": "查询采购申请列表",
        "QUERY_REQUISITION_DETAIL": lambda p: f"查询采购申请{p.get('banfn', '')}的详情",
        "QUERY_INFO_RECORD": "查询采购信息记录",
        "QUERY_MATERIAL_DOCUMENT": "查询物料凭证",
    }
    
    # FI Agent 操作映射
    fi_mappings = {
        "QUERY_DOCUMENT_LIST": "查询会计凭证列表",
        "QUERY_DOCUMENT_DETAIL": lambda p: f"查询会计凭证{p.get('belnr', '')}的详情",
        "CREATE_DOCUMENT": "创建会计凭证",
        "QUERY_ACCOUNT_LIST": "查询科目列表",
        "QUERY_ACCOUNT_BALANCE": lambda p: f"查询科目{p.get('saknr', '')}的余额",
        "QUERY_BALANCE_SHEET": "查询资产负债表",
        "QUERY_PROFIT_LOSS": "查询利润表",
        "QUERY_CASH_FLOW": "查询现金流量表",
        "START_MONTH_END": "启动月结",
        "QUERY_MONTH_END_STATUS": "查询月结状态",
    }
    
    # CO Agent 操作映射
    co_mappings = {
        "QUERY_COST_OBJECT_LIST": "查询成本对象列表",
        "QUERY_COST_OBJECT_DETAIL": lambda p: f"查询成本对象{p.get('orderNumber', '')}的详情",
        "QUERY_INTERNAL_ORDER_LIST": "查询内部订单列表",
        "QUERY_INTERNAL_ORDER_DETAIL": lambda p: f"查询内部订单{p.get('orderNumber', '')}的详情",
        "QUERY_SETTLEMENT_RULES": "查询结算规则",
        "CO_MONTH_END": "启动CO月结",
        "QUERY_CO_MONTH_END_STATUS": "查询CO月结状态",
    }
    
    mappings = {
        "sd": sd_mappings,
        "pp": pp_mappings,
        "mm": mm_mappings,
        "fi": fi_mappings,
        "co": co_mappings,
    }
    
    agent_mappings = mappings.get(agent_name, {})
    mapping = agent_mappings.get(action_code)
    
    if mapping is None:
        return None
    
    if callable(mapping):
        return mapping(params)
    
    return mapping
