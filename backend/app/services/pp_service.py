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
    
    def set_token(self, token: str):
        """设置认证token"""
        self.token = token
        
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
        url = f"{self.base_url}{path}"
        
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
        
        # 重试逻辑
        last_error = None
        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"调用PP服务: {method} {path} (尝试 {attempt + 1}/{self.retry_count})")
                    
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
        return await self._request("GET", "/sinocst-module-pp/productOrder/detail", params={"aufnr": aufnr})
    
    async def get_unreported_work_list(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询未报工情况列表
        
        Args:
            params: 查询参数（工厂、订单号、物料号等）
        
        Returns:
            未报工情况列表数据
        """
        return await self._request("GET", "/sinocst-module-pp/workReport/unreported", params=params)
    
    async def get_work_report_list(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        查询报工一览表
        
        Args:
            params: 查询参数
        
        Returns:
            报工一览表数据
        """
        return await self._request("GET", "/sinocst-module-pp/workReport/list", params=params)
    
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
        return await self._request("GET", "/sinocst-module-pp/productOrder/status", params={"aufnr": aufnr})

