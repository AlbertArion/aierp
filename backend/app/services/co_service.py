"""
CO模块服务客户端
用于调用ai_erp_standard-v2507服务的CO模块接口
"""
import httpx
import asyncio
import logging
from typing import Dict, Any, Optional, List
from app.config.co_config import COConfig

logger = logging.getLogger(__name__)

class COService:
    """CO模块服务客户端"""
    
    def __init__(self):
        self.base_url = COConfig.BASE_URL
        self.timeout = COConfig.TIMEOUT
        self.retry_count = COConfig.RETRY_COUNT
        self.token = None  # 用户token，从请求中获取
        self.mandt = None  # 集团代码（mandt），从请求头X-Mandt或X-Tenant-Id获取
        self.tenant_id = None  # 租户ID，从请求头X-Tenant-Id获取
        # 判断是否通过网关访问（网关端口通常是9015）
        self.is_gateway = "9015" in self.base_url or "gateway" in self.base_url.lower()
        # 网关地址（用于跨服务请求）
        self.gateway_url = "http://localhost:9015"
        # 其他服务的直接访问地址
        self.service_urls = {
            "sinocst-master-data": "http://localhost:9100",
            "sinocst-module-pp": "http://localhost:9110",
            "sinocst-module-sd": "http://localhost:9106",
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
        - 通过网关访问时，路径需要包含服务名称前缀 /sinocst-module-co/
        - 直接访问服务时，路径保持原样（因为后端Controller已经定义了完整的路径映射）
        """
        if self.is_gateway:
            # 通过网关访问，确保路径包含服务名称前缀
            if not path.startswith("/sinocst-module-co/"):
                if path.startswith("/sinocst-module-co"):
                    return path
                path = path.lstrip("/")
                return f"/sinocst-module-co/{path}"
            return path
        else:
            # 直接访问服务，保留路径原样
            # 注意：后端Controller中有些路径需要 /sinocst-module-co/ 前缀（如月结流程），
            # 有些路径不需要（如 /pc/cost-object），所以不在这里处理，保持原样
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
                    adjusted_path = path
                    logger.info(f"跨服务请求（通过网关）: {service_name} -> {self.gateway_url}{adjusted_path}")
                    return self.gateway_url, adjusted_path
                else:
                    adjusted_path = path.replace(f"/{service_name}/", "/", 1)
                    logger.info(f"跨服务请求（直接访问）: {service_name} -> {service_url}{adjusted_path}")
                    return service_url, adjusted_path
        
        # CO模块请求，使用配置的base_url
        if self.is_gateway:
            return self.base_url, path
        else:
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
        request_headers = COConfig.get_headers(headers)
        
        # 如果设置了token，添加到请求头
        if self.token:
            token_value = self.token
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]
            elif token_value.lower().startswith("crypto "):
                pass
            
            token_value = token_value.strip()
            request_headers["Blade-Auth"] = f"bearer {token_value}"
            logger.info(f"已添加Blade-Auth头到CO服务请求 (token长度: {len(token_value)})")
        elif COConfig.API_TOKEN:
            token_value = COConfig.API_TOKEN
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]
            token_value = token_value.strip()
            request_headers["Blade-Auth"] = f"bearer {token_value}"
            logger.info("使用配置的API_TOKEN")
        else:
            logger.warning("未设置token，CO服务请求可能失败")
        
        # 添加租户信息请求头
        if self.mandt:
            request_headers["X-Mandt"] = self.mandt
            logger.info(f"添加X-Mandt请求头: {self.mandt}")
        
        if self.tenant_id:
            request_headers["X-Tenant-Id"] = self.tenant_id
            logger.info(f"添加X-Tenant-Id请求头: {self.tenant_id}")
        
        # 重试逻辑
        last_exception = None
        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"CO服务请求 [{attempt + 1}/{self.retry_count}]: {method} {url}")
                    if params:
                        logger.debug(f"请求参数: {params}")
                    if json:
                        logger.debug(f"请求体: {json}")
                    
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json,
                        headers=request_headers
                    )
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    logger.info(f"CO服务请求成功: {method} {url}, 状态码: {response.status_code}")
                    return result
                    
            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(f"CO服务请求超时 [{attempt + 1}/{self.retry_count}]: {method} {url}, 错误: {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(1 * (attempt + 1))  # 递增延迟
                    continue
                else:
                    raise Exception(f"CO服务请求超时（已重试{self.retry_count}次）: {str(e)}")
                    
            except httpx.HTTPStatusError as e:
                last_exception = e
                error_msg = f"CO服务请求失败 [{attempt + 1}/{self.retry_count}]: {method} {url}, 状态码: {e.response.status_code}"
                try:
                    error_body = e.response.json()
                    error_msg += f", 错误信息: {error_body}"
                except:
                    error_body = e.response.text
                    error_msg += f", 响应内容: {error_body[:200]}"
                
                logger.error(error_msg)
                
                # 4xx错误不重试（客户端错误）
                if 400 <= e.response.status_code < 500:
                    raise Exception(error_msg)
                
                # 5xx错误重试（服务器错误）
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                else:
                    raise Exception(error_msg)
                    
            except Exception as e:
                last_exception = e
                logger.error(f"CO服务请求异常 [{attempt + 1}/{self.retry_count}]: {method} {url}, 错误: {str(e)}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                else:
                    raise Exception(f"CO服务请求失败（已重试{self.retry_count}次）: {str(e)}")
        
        # 所有重试都失败
        if last_exception:
            raise last_exception
        else:
            raise Exception(f"CO服务请求失败: {method} {url}")
    
    # ========== 成本对象相关方法 ==========
    
    async def get_cost_object_list(
        self,
        current: int = 1,
        size: int = 10,
        order_number: Optional[str] = None,
        matnr: Optional[str] = None,
        werks: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        查询成本对象列表
        
        Args:
            current: 当前页（后端不支持分页，仅用于前端展示）
            size: 每页大小（后端不支持分页，仅用于前端展示）
            order_number: 生产订单号（可选）
            matnr: 物料号（可选）
            werks: 工厂（可选）
        
        Returns:
            成本对象列表数据
        """
        params = {}
        
        # 后端API参数名是 order，不是 aufnr
        if order_number:
            params["order"] = order_number
        if matnr:
            params["matnr"] = matnr
        if werks:
            params["werks"] = werks
        
        # 添加其他查询参数（如 fiscalYear, periodFrom, periodTo）
        params.update({k: v for k, v in kwargs.items() if v is not None})
        
        # 使用正确的后端端点：/pc/cost-object/overview
        path = "/pc/cost-object/overview"
        return await self._request("GET", path, params=params)
    
    async def get_cost_object_detail(self, order_number: str) -> Dict[str, Any]:
        """
        查询成本对象详情
        
        Args:
            order_number: 生产订单号
        
        Returns:
            成本对象详情数据
        """
        # 使用正确的后端端点：/pc/cost-object/detail
        path = "/pc/cost-object/detail"
        # 后端API参数名是 order，不是 aufnr
        params = {"order": order_number}
        return await self._request("GET", path, params=params)
    
    async def settle_cost_object(
        self,
        order_number: str,
        settlement_date: Optional[str] = None,
        settle_rule: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        成本对象结算（生产订单完工后结算）
        
        Args:
            order_number: 生产订单号
            settlement_date: 结算日期（格式：yyyy-MM-dd，可选）
            settle_rule: 结算规则（可选，默认：INVENTORY-结算到库存）
        
        Returns:
            结算结果（包含FI凭证号）
        """
        settlement_data = {
            "orderNumber": order_number,
            "settlementDate": settlement_date,
            "settleRule": settle_rule or "INVENTORY",
            "settleTo": "INVENTORY",
        }
        settlement_data.update({k: v for k, v in kwargs.items() if v is not None})
        
        path = "/auto-posting/cost-object/settle"
        return await self._request("POST", path, json=settlement_data)
    
    # ========== 内部订单相关方法 ==========
    
    async def get_internal_order_list(
        self,
        current: int = 1,
        size: int = 10,
        order_number: Optional[str] = None,
        controlling_area: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        查询内部订单列表
        
        Args:
            current: 当前页
            size: 每页大小
            order_number: 内部订单号（可选）
            controlling_area: 控制范围（可选）
        
        Returns:
            内部订单列表数据
        """
        params = {
            "current": current,
            "size": size,
        }
        
        if order_number:
            params["aufnr"] = order_number
        if controlling_area:
            params["kokrs"] = controlling_area
        
        params.update({k: v for k, v in kwargs.items() if v is not None})
        
        path = "/internal-order/list"
        return await self._request("GET", path, params=params)
    
    async def get_internal_order_detail(
        self,
        order_number: str,
        controlling_area: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        查询内部订单详情
        
        Args:
            order_number: 内部订单号
            controlling_area: 控制范围（可选）
        
        Returns:
            内部订单详情数据
        """
        path = f"/internal-order/detail"
        params = {"aufnr": order_number}
        if controlling_area:
            params["kokrs"] = controlling_area
        return await self._request("GET", path, params=params)
    
    async def explode_bom_tree_for_internal_order(
        self,
        order_number: str,
        matnr: Optional[str] = None,
        werks: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        内部订单BOM树形展开
        
        Args:
            order_number: 内部订单号
            matnr: 物料号（可选，如果为空则从订单获取）
            werks: 工厂（可选，如果为空则从订单获取）
        
        Returns:
            BOM树形结构数据
        """
        path = f"/internal-order/{order_number}/bom-explode"
        json_data = {}
        if matnr:
            json_data["matnr"] = matnr
        if werks:
            json_data["werks"] = werks
        return await self._request("POST", path, json=json_data if json_data else None)
    
    async def settle_internal_order(
        self,
        order_number: str,
        controlling_area: Optional[str] = None,
        settlement_target_type: Optional[str] = None,
        settlement_target: Optional[str] = None,
        settlement_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        内部订单结算
        
        Args:
            order_number: 内部订单号
            controlling_area: 控制范围（可选）
            settlement_target_type: 结算目标类型（可选，默认：COST_CENTER-成本中心）
            settlement_target: 结算目标（成本中心号或科目代码，可选）
            settlement_date: 结算日期（格式：yyyy-MM-dd，可选）
        
        Returns:
            结算结果（包含FI凭证号）
        """
        settlement_data = {
            "orderNumber": order_number,
            "controllingArea": controlling_area,
            "settlementTargetType": settlement_target_type or "COST_CENTER",
            "settlementTarget": settlement_target,
            "settlementDate": settlement_date,
        }
        settlement_data.update({k: v for k, v in kwargs.items() if v is not None})
        
        path = "/internal-order/settlement/execute"
        return await self._request("POST", path, json=settlement_data)
    
    # ========== CO-PA相关方法 ==========
    
    async def get_pa_revenue_list(
        self,
        current: int = 1,
        size: int = 10,
        fiscal_year: Optional[str] = None,
        period: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        查询CO-PA销售收入列表
        
        Args:
            current: 当前页
            size: 每页大小
            fiscal_year: 会计年度（可选）
            period: 会计期间（可选）
        
        Returns:
            CO-PA销售收入列表数据
        """
        params = {
            "current": current,
            "size": size,
        }
        
        if fiscal_year:
            params["gjahr"] = fiscal_year
        if period:
            params["perio"] = period
        
        params.update({k: v for k, v in kwargs.items() if v is not None})
        
        path = "/pa/revenue/list"
        return await self._request("GET", path, params=params)
    
    async def get_pa_cost_list(
        self,
        current: int = 1,
        size: int = 10,
        fiscal_year: Optional[str] = None,
        period: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        查询CO-PA销售成本列表
        
        Args:
            current: 当前页
            size: 每页大小
            fiscal_year: 会计年度（可选）
            period: 会计期间（可选）
        
        Returns:
            CO-PA销售成本列表数据
        """
        params = {
            "current": current,
            "size": size,
        }
        
        if fiscal_year:
            params["gjahr"] = fiscal_year
        if period:
            params["perio"] = period
        
        params.update({k: v for k, v in kwargs.items() if v is not None})
        
        path = "/pa/cost/list"
        return await self._request("GET", path, params=params)
    
    # ========== CO月结相关方法 ==========
    
    async def execute_all_co_closing_steps(
        self,
        controlling_area: str,
        fiscal_year: int,
        period: int,
        test_run: bool = False
    ) -> Dict[str, Any]:
        """
        执行所有CO月结步骤
        
        Args:
            controlling_area: 成本控制范围
            fiscal_year: 会计年度
            period: 会计期间（1-12）
            test_run: 是否试运行（默认False）
        
        Returns:
            所有步骤执行结果
        """
        return await self._request(
            method="POST",
            path="/sinocst-module-co/period-closing-process/execute-all-steps",
            params={
                "controllingArea": controlling_area,
                "fiscalYear": fiscal_year,
                "period": period,
                "testRun": test_run
            }
        )
    
    async def execute_co_closing_step(
        self,
        controlling_area: str,
        fiscal_year: int,
        period: int,
        step_code: str,
        test_run: bool = False
    ) -> Dict[str, Any]:
        """
        执行单个CO月结步骤
        
        Args:
            controlling_area: 成本控制范围
            fiscal_year: 会计年度
            period: 会计期间（1-12）
            step_code: 步骤代码（KSU5/KSV5/KO8G/AIAB/AIBU）
            test_run: 是否试运行（默认False）
        
        Returns:
            步骤执行结果
        """
        return await self._request(
            method="POST",
            path="/sinocst-module-co/period-closing-process/execute-step",
            params={
                "controllingArea": controlling_area,
                "fiscalYear": fiscal_year,
                "period": period,
                "stepCode": step_code,
                "testRun": test_run
            }
        )
    
    async def get_co_closing_process_status(
        self,
        controlling_area: str,
        fiscal_year: int,
        period: int
    ) -> Dict[str, Any]:
        """
        查询CO月结流程状态
        
        Args:
            controlling_area: 成本控制范围
            fiscal_year: 会计年度
            period: 会计期间（1-12）
        
        Returns:
            CO月结流程状态信息
        """
        return await self._request(
            method="GET",
            path="/sinocst-module-co/period-closing-process/process-status",
            params={
                "controllingArea": controlling_area,
                "fiscalYear": fiscal_year,
                "period": period
            }
        )
