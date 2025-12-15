"""
MM模块服务客户端
用于调用ai_erp_standard-v2507服务的MM模块接口
"""
import httpx
import asyncio
import logging
from typing import Dict, Any, Optional, List
from app.config.mm_config import MMConfig

logger = logging.getLogger(__name__)

class MMService:
    """MM模块服务客户端"""
    
    def __init__(self):
        self.base_url = MMConfig.BASE_URL
        self.timeout = MMConfig.TIMEOUT
        self.retry_count = MMConfig.RETRY_COUNT
        self.token = None  # 用户token，从请求中获取
        self.mandt = None  # 集团代码（mandt），从请求头X-Mandt或X-Tenant-Id获取
        self.tenant_id = None  # 租户ID，从请求头X-Tenant-Id获取
        # 判断是否通过网关访问
        self.is_gateway = "9015" in self.base_url or "gateway" in self.base_url.lower()
        # 网关地址（用于跨服务请求）
        self.gateway_url = "http://localhost:9015"
        # 其他服务的直接访问地址
        self.service_urls = {
            "sinocst-master-data": "http://localhost:9100",
        }
    
    def set_token(self, token: str):
        """设置认证token"""
        self.token = token
    
    def set_mandt(self, mandt: str):
        """设置集团代码（mandt）"""
        self.mandt = mandt
    
    def set_tenant_id(self, tenant_id: str):
        """设置租户ID"""
        self.tenant_id = tenant_id
    
    def _build_path(self, path: str) -> str:
        """
        根据BASE_URL构建正确的路径
        - 通过网关访问时，路径需要包含服务名称前缀 /sinocst-module-mm/ 或 /sinocst-master-data/
        - 直接访问服务时，路径不需要服务名称前缀
        """
        if self.is_gateway:
            return path
        else:
            # 直接访问服务，移除服务名称前缀
            for service_prefix in ["/sinocst-module-mm/", "/sinocst-master-data/"]:
                if path.startswith(service_prefix):
                    return path.replace(service_prefix, "/", 1)
            for service_prefix in ["/sinocst-module-mm", "/sinocst-master-data"]:
                if path.startswith(service_prefix):
                    return path.replace(service_prefix, "", 1)
            return path
    
    def _get_service_url(self, path: str) -> tuple:
        """
        根据请求路径获取正确的服务URL和调整后的路径
        
        Args:
            path: 请求路径
        
        Returns:
            (base_url, adjusted_path) 元组
        """
        # 检查是否是跨服务请求（访问其他模块）
        for service_name, service_url in self.service_urls.items():
            if path.startswith(f"/{service_name}/"):
                # 跨服务请求
                if self.is_gateway:
                    # 通过网关访问，路径保持原样（网关会自动路由到对应服务）
                    adjusted_path = path
                    logger.info(f"跨服务请求（通过网关）: {service_name} -> {self.gateway_url}{adjusted_path}")
                    return self.gateway_url, adjusted_path
                else:
                    # 直接访问服务，使用该服务的直接地址
                    # 移除服务名前缀
                    adjusted_path = path.replace(f"/{service_name}/", "/", 1)
                    logger.info(f"跨服务请求（直接访问）: {service_name} -> {service_url}{adjusted_path}")
                    return service_url, adjusted_path
        
        # MM模块请求，使用配置的base_url
        if self.is_gateway:
            return self.base_url, path
        else:
            # 直接访问时，使用_build_path调整路径
            return self.base_url, self._build_path(path)
    
    async def _request(
        self, 
        method: str, 
        path: str, 
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        统一的HTTP请求方法，支持重试和错误处理
        
        Args:
            method: HTTP方法（GET, POST, PUT, DELETE等）
            path: 请求路径（相对于base_url）
            params: URL参数
            json: JSON请求体
            headers: 额外的请求头
        
        Returns:
            响应数据的字典
        
        Raises:
            Exception: 请求失败时抛出异常
        """
        # 根据路径获取正确的服务URL
        base_url, adjusted_path = self._get_service_url(path)
        url = f"{base_url}{adjusted_path}"
        
        # 获取请求头
        request_headers = MMConfig.get_headers(headers)
        
        # 如果设置了token，添加到请求头
        if self.token:
            token_value = self.token
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]
            token_value = token_value.strip()
            request_headers["Blade-Auth"] = f"bearer {token_value}"
            logger.info(f"已添加Blade-Auth头到MM服务请求 (token长度: {len(token_value)})")
        elif MMConfig.API_TOKEN:
            token_value = MMConfig.API_TOKEN
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]
            token_value = token_value.strip()
            request_headers["Blade-Auth"] = f"bearer {token_value}"
            logger.info("使用配置的API_TOKEN")
        else:
            logger.warning("未设置token，MM服务请求可能失败")
        
        # 添加mandt和tenantId到请求头（如果设置了）
        if self.mandt:
            request_headers["X-Mandt"] = self.mandt
            logger.info(f"已添加X-Mandt头: {self.mandt}")
        if self.tenant_id:
            request_headers["X-Tenant-Id"] = self.tenant_id
            logger.info(f"已添加X-Tenant-Id头: {self.tenant_id}")
        
        # 重试逻辑
        last_error = None
        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"调用MM服务: {method} {path} (尝试 {attempt + 1}/{self.retry_count})")
                    logger.info(f"请求参数: {params}")
                    
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json,
                        headers=request_headers
                    )
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    # 检查result是否为None
                    if result is None:
                        logger.warning(f"MM服务响应为空: {path}")
                        return {"code": 200, "success": True, "data": None, "msg": "响应数据为空"}
                    
                    # 确保result是字典类型
                    if not isinstance(result, dict):
                        logger.warning(f"MM服务响应格式异常: {path}, 类型: {type(result)}")
                        return {"code": 200, "success": True, "data": result, "msg": "响应格式异常"}
                    
                    logger.info(f"MM服务响应成功: {path}, 响应类型: {type(result)}")
                    logger.debug(f"响应数据: {result}")
                    return result
                    
            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code
                
                # 获取错误信息
                error_data = {}
                try:
                    error_data = e.response.json()
                except:
                    error_data = {"msg": e.response.text or "请求错误"}
                
                error_msg = error_data.get("msg", f"HTTP {status_code} 错误")
                
                if 400 <= status_code < 500:
                    logger.error(f"MM服务请求错误: {path}, 状态码: {status_code}, 错误: {error_msg}")
                    
                    if status_code == 401:
                        raise Exception(f"MM服务认证失败: {error_msg}")
                    else:
                        raise Exception(f"{error_msg}")
                
                # 5xx错误重试
                logger.warning(f"MM服务请求失败: {path}, 状态码: {status_code}, 错误: {error_msg}")
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.warning(f"MM服务请求失败，{wait_time}秒后重试: {path}")
                    await asyncio.sleep(wait_time)
                else:
                    raise Exception(f"MM服务请求失败: {error_msg}")
                    
            except httpx.RequestError as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"MM服务网络错误，{wait_time}秒后重试: {path}")
                    await asyncio.sleep(wait_time)
                else:
                    raise Exception(f"MM服务网络错误: {str(e)}")
        
        raise Exception(f"MM服务请求失败: {str(last_error)}")
    
    async def get_purchase_order_list(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询采购订单列表
        
        Args:
            params: 查询参数（订单号、供应商、工厂等）
        
        Returns:
            采购订单列表数据
        """
        return await self._request("GET", "/sinocst-master-data/sinocst-ekko/ekko/page", params=params)
    
    async def get_purchase_order_detail(self, ebeln: str) -> Dict[str, Any]:
        """
        查询采购订单详情
        
        Args:
            ebeln: 采购订单号
        
        Returns:
            采购订单详情数据
        """
        return await self._request("GET", "/sinocst-master-data/sinocst-ekko/ekko/detail", params={"ebeln": ebeln})
    
    async def get_purchase_requisition_list(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询采购申请列表
        
        Args:
            params: 查询参数
        
        Returns:
            采购申请列表数据
        """
        return await self._request("GET", "/sinocst-module-mm/eban/page", params=params)
    
    async def get_purchase_requisition_detail(self, banfn: str) -> Dict[str, Any]:
        """
        查询采购申请详情
        
        Args:
            banfn: 采购申请号
        
        Returns:
            采购申请详情数据
        """
        return await self._request("GET", "/sinocst-module-mm/eban/detail", params={"banfn": banfn})
    
    async def get_purchase_info_record_list(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询采购信息记录列表
        
        Args:
            params: 查询参数
        
        Returns:
            采购信息记录列表数据
        """
        return await self._request("GET", "/sinocst-master-data/sinocst-eina/eina/page", params=params)
    
    async def get_purchase_info_record_detail(self, infnr: str) -> Dict[str, Any]:
        """
        查询采购信息记录详情
        
        Args:
            infnr: 采购信息记录号
        
        Returns:
            采购信息记录详情数据
        """
        return await self._request("GET", "/sinocst-master-data/sinocst-eina/eina/detail", params={"infnr": infnr})
    
    async def get_material_document_list(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询物料凭证列表
        
        Args:
            params: 查询参数
        
        Returns:
            物料凭证列表数据
        """
        return await self._request("GET", "/sinocst-master-data/sinocst-mkpf/mkpf/page", params=params)
    
    async def get_material_document_detail(self, mblnr: str, mjahr: str) -> Dict[str, Any]:
        """
        查询物料凭证详情
        
        Args:
            mblnr: 物料凭证号
            mjahr: 物料凭证年度
        
        Returns:
            物料凭证详情数据
        """
        return await self._request("GET", "/sinocst-master-data/sinocst-mkpf/mkpf/detail", params={"mblnr": mblnr, "mjahr": mjahr})

