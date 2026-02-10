#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ERP服务客户端
用于调用Java后端各个模块的服务接口，获取业务数据
"""

import httpx
import asyncio
import logging
from typing import Dict, Any, Optional, List
from app.config.sd_config import SDConfig

logger = logging.getLogger(__name__)


class ERPServiceClient:
    """ERP服务客户端，用于调用Java后端服务（带连接池复用）"""

    # 类级别共享连接池，避免每次请求创建新连接
    _shared_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def _get_shared_client(cls) -> httpx.AsyncClient:
        """获取/创建共享的 httpx.AsyncClient（带连接池）"""
        if cls._shared_client is None or cls._shared_client.is_closed:
            cls._shared_client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(
                    max_connections=50,          # 最大连接数
                    max_keepalive_connections=20, # 保持活跃的连接数
                    keepalive_expiry=30,          # 空闲连接过期时间(秒)
                ),
                http2=False,  # Java后端通常不支持HTTP/2
            )
        return cls._shared_client

    @classmethod
    async def close_shared_client(cls):
        """关闭共享客户端（用于应用关闭时清理）"""
        if cls._shared_client and not cls._shared_client.is_closed:
            await cls._shared_client.aclose()
            cls._shared_client = None
    
    def __init__(self, token: Optional[str] = None, mandt: Optional[str] = None, tenant_id: Optional[str] = None):
        """
        初始化ERP服务客户端
        
        Args:
            token: 认证token
            mandt: 集团代码
            tenant_id: 租户ID
        """
        # 判断是否通过网关访问（网关端口通常是9015）
        self.gateway_url = "http://localhost:9015"
        self.is_gateway = True  # 默认通过网关访问
        
        # 各服务的直接访问地址（如果直接访问）
        self.service_urls = {
            "sinocst-module-sd": "http://localhost:9105",  # SD模块
            "sinocst-module-pp": "http://localhost:9110",  # PP模块
            "sinocst-module-mm": "http://localhost:9108",  # MM模块
            "sinocst-module-wm": "http://localhost:9112",  # WM模块
            "sinocst-module-fa": "http://localhost:9998",  # FI模块
            "sinocst-module-co": "http://localhost:9997",  # CO模块
            "sinocst-master-data": "http://localhost:9100",  # 主数据模块
        }
        
        self.token = token
        self.mandt = mandt
        self.tenant_id = tenant_id
        self.timeout = 30.0
        self.retry_count = 3
    
    def set_token(self, token: str):
        """设置认证token"""
        self.token = token
    
    def set_mandt(self, mandt: str):
        """设置集团代码"""
        self.mandt = mandt
    
    def set_tenant_id(self, tenant_id: str):
        """设置租户ID"""
        self.tenant_id = tenant_id
    
    def _get_service_url(self, service_name: str, path: str) -> tuple:
        """
        获取服务URL和调整后的路径
        
        Args:
            service_name: 服务名称，如 "sinocst-module-wm"
            path: 请求路径
        
        Returns:
            (base_url, adjusted_path) 元组
        """
        if self.is_gateway:
            # 通过网关访问，路径需要包含服务名称前缀
            if not path.startswith(f"/{service_name}/"):
                path = path.lstrip("/")
                adjusted_path = f"/{service_name}/{path}"
            else:
                adjusted_path = path
            return self.gateway_url, adjusted_path
        else:
            # 直接访问服务
            service_url = self.service_urls.get(service_name)
            if not service_url:
                raise ValueError(f"未知的服务名称: {service_name}")
            # 移除服务名前缀（如果有）
            if path.startswith(f"/{service_name}/"):
                adjusted_path = path.replace(f"/{service_name}/", "/", 1)
            else:
                adjusted_path = path
            return service_url, adjusted_path
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = SDConfig.get_headers()
        
        # 添加认证token
        if self.token:
            token_value = self.token
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]
            token_value = token_value.strip()
            headers["Blade-Auth"] = f"bearer {token_value}"
        
        # 添加租户信息
        if self.mandt:
            headers["X-Mandt"] = self.mandt
        if self.tenant_id:
            headers["X-Tenant-Id"] = self.tenant_id
        elif self.mandt:
            headers["X-Tenant-Id"] = self.mandt
        
        return headers
    
    async def _request(
        self,
        service_name: str,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        统一的HTTP请求方法
        
        Args:
            service_name: 服务名称
            method: HTTP方法
            path: 请求路径
            params: URL参数
            json: JSON请求体
        
        Returns:
            响应数据
        """
        base_url, adjusted_path = self._get_service_url(service_name, path)
        url = f"{base_url}{adjusted_path}"
        headers = self._get_headers()
        
        client = self._get_shared_client()
        last_error = None
        for attempt in range(self.retry_count):
            try:
                logger.debug(f"调用{service_name}服务: {method} {url}")

                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers,
                    timeout=self.timeout,
                )

                response.raise_for_status()
                result = response.json()
                return result
                    
            except httpx.HTTPStatusError as e:
                last_error = e
                if 400 <= e.response.status_code < 500:
                    # 4xx错误不重试
                    error_data = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else {"msg": str(e)}
                    # 提取原始错误信息，不添加服务名前缀，以便后续错误处理能正确识别错误类型
                    error_msg = error_data.get('msg') or error_data.get('message') or str(e)
                    raise Exception(error_msg)
                
                # 5xx错误重试
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"{service_name}服务错误，{wait_time}秒后重试")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"{service_name}服务错误: {str(e)}")
            
            except Exception as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"{service_name}服务错误，{wait_time}秒后重试: {str(e)}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise
        
        if last_error:
            raise last_error
    
    # ========== WM模块（库存）相关方法 ==========
    
    async def get_inventory_data(
        self,
        matnr: Optional[str] = None,
        werks: Optional[str] = None,
        lgort: Optional[str] = None
    ) -> List[Dict]:
        """
        获取库存数据
        
        Args:
            matnr: 物料号
            werks: 工厂
            lgort: 库存地点
        
        Returns:
            库存数据列表
        """
        params = {}
        if matnr:
            params["matnr"] = matnr
        if werks:
            params["werks"] = werks
        if lgort:
            params["lgort"] = lgort
        
        # 调用WM模块的库存查询接口
        # 注意：实际接口路径需要根据Java后端实现调整
        result = await self._request(
            "sinocst-module-wm",
            "GET",
            "/warehouse/list-storage",
            params=params
        )
        
        # 解析响应数据
        if isinstance(result, dict):
            return result.get("data", [])
        return []
    
    async def get_total_inventory_value(self) -> float:
        """获取总库存价值"""
        inventory_list = await self.get_inventory_data()
        total_value = 0.0
        for item in inventory_list:
            # 假设响应中有labst（库存数量）和价格字段
            quantity = float(item.get("labst", 0) or 0)
            # 这里需要获取物料价格，可能需要调用主数据服务
            total_value += quantity
        return total_value
    
    # ========== SD模块（销售）相关方法 ==========
    
    async def get_sales_order_data(
        self,
        vbeln: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        获取销售订单数据
        
        Args:
            vbeln: 销售订单号
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            销售订单列表
        """
        params = {}
        if vbeln:
            params["vbeln"] = vbeln
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        
        result = await self._request(
            "sinocst-module-sd",
            "GET",
            "/sales-order/list",
            params=params
        )
        
        if isinstance(result, dict):
            return result.get("data", {}).get("records", [])
        return []
    
    async def get_delivery_data(
        self,
        vbeln: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        获取交货单数据
        
        Args:
            vbeln: 交货单号
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            交货单列表
        """
        params = {}
        if vbeln:
            params["vbeln"] = vbeln
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        
        result = await self._request(
            "sinocst-module-sd",
            "GET",
            "/delivery/list",
            params=params
        )
        
        if isinstance(result, dict):
            return result.get("data", {}).get("records", [])
        return []
    
    async def calculate_daily_sales(self, days: int = 30) -> float:
        """
        计算日均销售额
        
        Args:
            days: 天数，默认30天
        
        Returns:
            日均销售额
        """
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        deliveries = await self.get_delivery_data(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        
        total_sales = 0.0
        for delivery in deliveries:
            # 假设响应中有netwr（净价值）字段
            netwr = float(delivery.get("netwr", 0) or 0)
            total_sales += netwr
        
        return total_sales / days if days > 0 else 0.0
    
    # ========== MM模块（采购）相关方法 ==========
    
    async def get_purchase_order_data(
        self,
        ebeln: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        获取采购订单数据
        
        Args:
            ebeln: 采购订单号
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            采购订单列表
        """
        params = {}
        if ebeln:
            params["ebeln"] = ebeln
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        
        result = await self._request(
            "sinocst-module-mm",
            "GET",
            "/purchase-order/list",
            params=params
        )
        
        if isinstance(result, dict):
            return result.get("data", {}).get("records", [])
        return []
    
    # ========== PP模块（生产）相关方法 ==========
    
    async def get_production_order_data(
        self,
        aufnr: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        获取生产订单数据
        
        Args:
            aufnr: 生产订单号
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            生产订单列表
        """
        params = {}
        if aufnr:
            params["aufnr"] = aufnr
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        
        result = await self._request(
            "sinocst-module-pp",
            "GET",
            "/production-order/list",
            params=params
        )
        
        if isinstance(result, dict):
            return result.get("data", {}).get("records", [])
        return []

