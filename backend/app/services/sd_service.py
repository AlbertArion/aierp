"""
SD模块服务客户端
用于调用ai_erp_standard-v2507服务的SD模块接口
"""
import httpx
import asyncio
import logging
from typing import Dict, Any, Optional, List
from app.config.sd_config import SDConfig

logger = logging.getLogger(__name__)

class SDService:
    """SD模块服务客户端"""
    
    def __init__(self):
        self.base_url = SDConfig.BASE_URL
        self.timeout = SDConfig.TIMEOUT
        self.retry_count = SDConfig.RETRY_COUNT
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
        request_headers = SDConfig.get_headers(headers)
        
        # 如果设置了token，添加到请求头（优先使用用户token，其次使用配置的API_TOKEN）
        # 注意：网关需要Blade-Auth头，格式为 "bearer {token}"（小写bearer）
        if self.token:
            # 网关使用Blade-Auth头进行认证，格式：bearer {token}
            # 注意：如果token已经包含bearer前缀，需要去掉
            token_value = self.token
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]  # 去掉 "bearer " 前缀
            elif token_value.lower().startswith("crypto "):
                # 加密token保持原样
                pass
            
            # 确保token值去除前后空格
            token_value = token_value.strip()
            
            # 网关期望的Blade-Auth头格式：bearer {token}（小写bearer，注意空格）
            # 注意：网关主要使用Blade-Auth头进行认证，Authorization头用于OAuth2客户端认证（Basic格式）
            request_headers["Blade-Auth"] = f"bearer {token_value}"
            # 不覆盖Authorization头（保持Basic认证格式，用于OAuth2客户端认证）
            # Authorization头已经在SDConfig.get_headers()中设置为Basic格式
            logger.info(f"已添加Blade-Auth头到SD服务请求 (token长度: {len(token_value)}, 格式: bearer {{token}})")
            logger.debug(f"Blade-Auth头值: bearer {token_value[:20]}... (前20字符)")
        elif SDConfig.API_TOKEN:
            token_value = SDConfig.API_TOKEN
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]
            token_value = token_value.strip()
            request_headers["Blade-Auth"] = f"bearer {token_value}"
            # 不覆盖Authorization头（保持Basic认证格式）
            logger.info("使用配置的API_TOKEN")
        else:
            logger.warning("未设置token，SD服务请求可能失败")
        
        # 记录请求头信息（不记录完整token，避免泄露）
        header_info = {}
        for key, value in request_headers.items():
            if key.lower() in ["blade-auth", "authorization"]:
                # 只记录token的前10个字符和长度
                if value and len(value) > 10:
                    header_info[key] = f"{value[:10]}... (长度: {len(value)})"
                else:
                    header_info[key] = value
            else:
                header_info[key] = value
        logger.debug(f"SD服务请求头: {header_info}")
        
        # 重试逻辑（指数退避）
        last_error = None
        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"调用SD服务: {method} {path} (尝试 {attempt + 1}/{self.retry_count})")
                    
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json,
                        headers=request_headers
                    )
                    
                    # 检查HTTP状态码
                    response.raise_for_status()
                    
                    # 解析JSON响应
                    result = response.json()
                    logger.info(f"SD服务响应成功: {path}")
                    return result
                    
            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code
                
                # 4xx错误不重试
                if 400 <= status_code < 500:
                    error_data = {}
                    try:
                        error_data = e.response.json()
                    except:
                        error_data = {"msg": e.response.text or "请求错误"}
                    
                    error_msg = error_data.get("msg", f"HTTP {status_code} 错误")
                    # 记录更详细的错误信息
                    logger.error(f"SD服务请求错误: {path}, 状态码: {status_code}, 错误: {error_msg}")
                    logger.error(f"响应体: {error_data}")
                    logger.error(f"请求URL: {url}")
                    logger.error(f"请求方法: {method}")
                    logger.error(f"请求头（已脱敏）: {header_info}")
                    
                    # 对于401错误，提供更明确的错误提示
                    if status_code == 401:
                        raise Exception(f"SD服务认证失败: {error_msg}。请检查token是否有效、未过期，以及格式是否正确（应为bearer格式的JWT token）")
                    else:
                        raise Exception(f"SD服务错误: {error_msg}")
                
                # 5xx错误重试
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt  # 指数退避：1秒, 2秒, 4秒...
                    logger.warning(f"SD服务错误，{wait_time}秒后重试: {path}, 状态码: {status_code}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"SD服务请求失败（已重试{self.retry_count}次）: {path}, 状态码: {status_code}")
                    raise Exception(f"SD服务不可用: HTTP {status_code}")
                    
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"SD服务请求超时，{wait_time}秒后重试: {path}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"SD服务请求超时（已重试{self.retry_count}次）: {path}")
                    raise Exception("SD服务请求超时，请稍后重试")
                    
            except httpx.ConnectError as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"无法连接到SD服务，{wait_time}秒后重试: {path}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"无法连接到SD服务（已重试{self.retry_count}次）: {path}")
                    raise Exception("无法连接到SD服务，请检查服务是否启动")
                    
            except Exception as e:
                last_error = e
                logger.error(f"SD服务请求异常: {path}, 错误: {str(e)}")
                raise Exception(f"SD服务请求失败: {str(e)}")
        
        # 所有重试都失败
        raise Exception(f"SD服务请求失败: {str(last_error)}")
    
    async def get_order_list(
        self, 
        current: int = 1, 
        size: int = 10,
        **filters
    ) -> Dict[str, Any]:
        """
        获取销售订单列表
        
        Args:
            current: 当前页码
            size: 每页数量
            **filters: 其他筛选条件（如vbeln, kunnr等）
        
        Returns:
            订单列表数据
        """
        params = {
            "current": current,
            "size": size,
            **filters
        }
        # 通过网关访问时，路径需要包含服务名称前缀
        return await self._request(
            method="GET",
            path="/sinocst-module-sd/sinocst-vbak/vbak/list",
            params=params
        )
    
    async def get_order_detail(self, vbeln: str) -> Dict[str, Any]:
        """
        获取销售订单详情
        
        Args:
            vbeln: 销售订单号
        
        Returns:
            订单详情数据
        """
        # 通过网关访问时，路径需要包含服务名称前缀
        return await self._request(
            method="GET",
            path="/sinocst-module-sd/sinocst-vbak/vbak/detail",
            params={"vbeln": vbeln}
        )
    
    async def get_order_info_for_delivery(self, vbeln: str) -> Dict[str, Any]:
        """
        获取订单信息（用于创建交货单）
        
        Args:
            vbeln: 销售订单号
        
        Returns:
            订单信息数据（包含行项目等）
        """
        # 通过网关访问时，路径需要包含服务名称前缀
        # 注意：后端期望的参数名是 vgbel，不是 vbeln
        return await self._request(
            method="GET",
            path="/sinocst-module-sd/sinocst-vbak/vbak/getVbInfoBy",
            params={"vgbel": vbeln}
        )
    
    async def create_delivery(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建交货单（内部会进行ATP检查）
        
        Args:
            order_data: 订单数据（SdKoShowVO格式）
        
        Returns:
            交货单创建结果（包含交货单号）
        """
        # 交货单接口在主数据服务中，通过网关访问
        return await self._request(
            method="POST",
            path="/sinocst-master-data/likp/sd/save",
            json=order_data
        )

