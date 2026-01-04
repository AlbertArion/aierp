"""
PP模块服务客户端
用于调用ai_erp_standard-v2507服务的PP模块接口
"""
import httpx
import asyncio
import logging
from typing import Dict, Any, Optional, List
from app.config.pp_config import PPConfig

logger = logging.getLogger(__name__)

class PPService:
    """PP模块服务客户端"""
    
    def __init__(self):
        self.base_url = PPConfig.BASE_URL
        self.timeout = PPConfig.TIMEOUT
        self.retry_count = PPConfig.RETRY_COUNT
        self.token = None  # 用户token，从请求中获取
        self.mandt = None  # 集团代码，从请求中获取
        self.tenant_id = None  # 租户ID，从请求中获取
        # 判断是否通过网关访问
        self.is_gateway = "9015" in self.base_url or "gateway" in self.base_url.lower()
    
    def set_token(self, token: str):
        """设置认证token"""
        self.token = token
    
    def set_mandt(self, mandt: str):
        """设置集团代码"""
        self.mandt = mandt
    
    def set_tenant_id(self, tenant_id: str):
        """设置租户ID"""
        self.tenant_id = tenant_id
    
    def _build_path(self, path: str) -> str:
        """
        根据BASE_URL构建正确的路径
        - 通过网关访问时，路径需要包含服务名称前缀 /sinocst-module-pp/
        - 直接访问服务时，路径不需要服务名称前缀
        """
        if self.is_gateway:
            return path
        else:
            # 直接访问服务，移除服务名称前缀
            if path.startswith("/sinocst-module-pp/"):
                return path.replace("/sinocst-module-pp/", "/", 1)
            elif path.startswith("/sinocst-module-pp"):
                return path.replace("/sinocst-module-pp", "", 1)
            return path
    
    def _normalize_aufnr(self, aufnr: str) -> str:
        """
        规范化生产订单号格式
        SAP生产订单号通常是12位，但用户可能输入10位数字
        需要尝试两种格式：原格式和补零到12位
        
        Args:
            aufnr: 原始订单号
            
        Returns:
            规范化后的订单号（保持原格式，因为数据库可能存储的是10位）
        """
        if not aufnr:
            return aufnr
        
        # 去除空格
        aufnr = aufnr.strip()
        
        # 如果是纯数字且长度小于12，尝试补零到12位
        if aufnr.isdigit():
            # 先尝试原格式（10位），如果查询不到再尝试12位格式
            # 注意：数据库可能存储的是10位格式，所以先保持原格式
            return aufnr
        
        return aufnr
    
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
        # 根据是否通过网关访问调整路径
        adjusted_path = self._build_path(path)
        url = f"{self.base_url}{adjusted_path}"
        
        # 获取请求头
        request_headers = PPConfig.get_headers(headers)
        
        # 如果设置了token，添加到请求头
        if self.token:
            token_value = self.token
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]
            token_value = token_value.strip()
            request_headers["Blade-Auth"] = f"bearer {token_value}"
            logger.info(f"已添加Blade-Auth头到PP服务请求 (token长度: {len(token_value)})")
        elif PPConfig.API_TOKEN:
            token_value = PPConfig.API_TOKEN
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]
            token_value = token_value.strip()
            request_headers["Blade-Auth"] = f"bearer {token_value}"
            logger.info("使用配置的API_TOKEN")
        else:
            logger.warning("未设置token，PP服务请求可能失败")
        
        # 添加租户信息请求头（X-Mandt和X-Tenant-Id）
        # 这些请求头对于跨服务调用非常重要，确保下游服务能够正确获取租户信息
        if self.mandt:
            request_headers["X-Mandt"] = self.mandt
            logger.info(f"已添加X-Mandt头到请求: {self.mandt}")
        
        if self.tenant_id:
            request_headers["X-Tenant-Id"] = self.tenant_id
            logger.info(f"已添加X-Tenant-Id头到请求: {self.tenant_id}")
        elif self.mandt:
            # 如果没有tenantId但有mandt，使用mandt作为tenantId（通常它们是同一个值）
            request_headers["X-Tenant-Id"] = self.mandt
            logger.info(f"已添加X-Tenant-Id头到请求（使用mandt值）: {self.mandt}")
        
        # 重试逻辑
        last_error = None
        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"调用PP服务: {method} {path} (尝试 {attempt + 1}/{self.retry_count})")
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
                        logger.warning(f"PP服务响应为空: {path}")
                        return {"code": 200, "success": True, "data": None, "msg": "响应数据为空"}
                    
                    # 确保result是字典类型
                    if not isinstance(result, dict):
                        logger.warning(f"PP服务响应格式异常: {path}, 类型: {type(result)}")
                        return {"code": 200, "success": True, "data": result, "msg": "响应格式异常"}
                    
                    logger.info(f"PP服务响应成功: {path}, 响应类型: {type(result)}")
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
                    logger.error(f"PP服务请求错误: {path}, 状态码: {status_code}, 错误: {error_msg}")
                    
                    if status_code == 401:
                        raise Exception(f"PP服务认证失败: {error_msg}")
                    else:
                        raise Exception(f"{error_msg}")
                
                # 5xx错误重试
                logger.warning(f"PP服务请求失败: {path}, 状态码: {status_code}, 错误: {error_msg}")
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.warning(f"PP服务请求失败，{wait_time}秒后重试: {path}")
                    await asyncio.sleep(wait_time)
                else:
                    raise Exception(f"PP服务请求失败: {error_msg}")
                    
            except httpx.RequestError as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"PP服务网络错误，{wait_time}秒后重试: {path}")
                    await asyncio.sleep(wait_time)
                else:
                    raise Exception(f"PP服务网络错误: {str(e)}")
        
        raise Exception(f"PP服务请求失败: {str(last_error)}")
    
    async def get_order_list(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询生产订单列表
        
        Args:
            params: 查询参数（订单号、物料号、工厂等）
        
        Returns:
            订单列表数据
        """
        # 使用listV2接口，查询条件更宽松，适合查看所有生产订单
        # 通过网关访问，需要加上服务名称前缀 sinocst-module-pp
        return await self._request("GET", "/sinocst-module-pp/sinocst-afko/afko/listV2", params=params)
    
    async def get_order_detail(self, aufnr: str) -> Dict[str, Any]:
        """
        查询生产订单详情
        
        Args:
            aufnr: 生产订单号
        
        Returns:
            订单详情数据
        """
        # 规范化订单号格式
        normalized_aufnr = self._normalize_aufnr(aufnr)
        logger.info(f"查询生产订单详情: 原始订单号={aufnr}, 规范化后={normalized_aufnr}")
        
        # 先尝试原格式查询
        result = await self._request("GET", "/sinocst-module-pp/productOrder/detail", params={"aufnr": normalized_aufnr})
        
        # 检查返回的数据是否为空
        if result and result.get("code") == 200:
            data = result.get("data", {})
            # 如果数据为空或关键字段为空，尝试12位格式
            if not data or (isinstance(data, dict) and not data.get("aufnr")):
                # 如果原格式是10位数字，尝试补零到12位
                if normalized_aufnr.isdigit() and len(normalized_aufnr) == 10:
                    padded_aufnr = normalized_aufnr.zfill(12)
                    logger.info(f"原格式查询无数据，尝试12位格式: {padded_aufnr}")
                    result = await self._request("GET", "/sinocst-module-pp/productOrder/detail", params={"aufnr": padded_aufnr})
                # 如果原格式是12位，尝试去掉前导零
                elif normalized_aufnr.isdigit() and len(normalized_aufnr) == 12:
                    # 去掉前导零，但保留至少10位
                    trimmed_aufnr = normalized_aufnr.lstrip('0')
                    if len(trimmed_aufnr) < 10:
                        trimmed_aufnr = trimmed_aufnr.zfill(10)
                    logger.info(f"12位格式查询无数据，尝试去掉前导零: {trimmed_aufnr}")
                    result = await self._request("GET", "/sinocst-module-pp/productOrder/detail", params={"aufnr": trimmed_aufnr})
        
        return result
    
    async def get_unreported_work_list(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询未报工情况列表
        
        Args:
            params: 查询参数（工厂、订单号、物料号等）
        
        Returns:
            未报工情况列表数据
        """
        # 如果参数中有aufnr，规范化订单号
        if params and "aufnr" in params:
            params["aufnr"] = self._normalize_aufnr(params["aufnr"])
        
        return await self._request("GET", "/sinocst-module-pp/workReport/unreported", params=params)
    
    async def get_work_report_list(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询报工一览表
        
        Args:
            params: 查询参数
        
        Returns:
            报工一览表数据
        """
        # 如果参数中有aufnr，规范化订单号
        if params and "aufnr" in params:
            params["aufnr"] = self._normalize_aufnr(params["aufnr"])
        
        return await self._request("GET", "/sinocst-module-pp/workReport/list", params=params)
    
    async def get_reported_work_list(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询已报工情况列表（确认数量=目标数量）
        
        Args:
            params: 查询参数（工厂、订单号、物料号等）
        
        Returns:
            已报工情况列表数据
        """
        # 如果参数中有aufnr，规范化订单号
        if params and "aufnr" in params:
            params["aufnr"] = self._normalize_aufnr(params["aufnr"])
        
        return await self._request("GET", "/sinocst-module-pp/workReport/reported", params=params)
    
    async def month_end_check(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        月结异常检测
        
        Args:
            params: 检测参数
        
        Returns:
            异常检测结果
        """
        return await self._request("POST", "/sinocst-module-pp/ai/month-end-check", json=params or {})
    
    async def get_order_status(self, aufnr: str) -> Dict[str, Any]:
        """
        查询生产订单状态
        
        Args:
            aufnr: 生产订单号
        
        Returns:
            订单状态数据
        """
        # 规范化订单号格式
        normalized_aufnr = self._normalize_aufnr(aufnr)
        return await self._request("GET", "/sinocst-module-pp/productOrder/status", params={"aufnr": normalized_aufnr})
    
    async def create_production_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建生产订单
        
        Args:
            order_data: 生产订单数据，包含以下字段：
                - matnr: 物料号（必填）
                - werks: 工厂（必填）
                - gamng: 订单数量（必填）
                - gmein: 基本计量单位（可选，默认PC）
                - auart: 订单类型（可选，默认PP01）
                - kdauf: 销售订单号（可选）
                - kdpos: 销售订单行项目号（可选）
                - gstrp: 基本开始日期（可选）
                - gltrp: 基本完成日期（可选）
                - internal: 是否内部生产订单（可选，默认False）
        
        Returns:
            创建结果，包含订单号（aufnr）
        """
        return await self._request("POST", "/sinocst-module-pp/productOrder/add", json=order_data)