from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from ...repository.orders_repo import search_orders as repo_search_orders, update_order_field as repo_update_order_field
from .auth import require_role
from fastapi import Depends

# 说明：订单协同模块接口，占位实现

router = APIRouter()


class OrderSearchRequest(BaseModel):
    keyword: str = Field("", description="订单检索关键词")
    page: int = 1
    size: int = 10


class OrderUpdateRequest(BaseModel):
    order_id: str
    field: str
    value: Any


@router.get("/search")
async def search_orders(keyword: Optional[str] = None, page: int = 1, size: int = 10) -> Dict[str, Any]:
    data = repo_search_orders(keyword, page, size)
    return {"items": data["items"], "total": data["total"], "page": page, "size": size, "keyword": keyword}


@router.put("/update")
async def update_order(payload: OrderUpdateRequest, _user=Depends(require_role("admin"))) -> Dict[str, Any]:
    updated = repo_update_order_field(payload.order_id, payload.field, payload.value)
    return {"updated": updated, "order_id": payload.order_id, "field": payload.field}


