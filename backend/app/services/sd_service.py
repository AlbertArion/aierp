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
        self.mandt = None  # 集团代码（mandt），从请求头X-Mandt或X-Tenant-Id获取
        self.tenant_id = None  # 租户ID，从请求头X-Tenant-Id获取
        # 判断是否通过网关访问（网关端口通常是9015）
        self.is_gateway = "9015" in self.base_url or "gateway" in self.base_url.lower()
        # 网关地址（用于跨服务请求，如访问WM、master-data等）
        self.gateway_url = "http://localhost:9015"
        # 其他服务的直接访问地址
        self.service_urls = {
            "sinocst-module-wm": "http://localhost:9112",
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
        - 通过网关访问时，路径需要包含服务名称前缀 /sinocst-module-sd/
        - 直接访问服务时，路径不需要服务名称前缀
        """
        if self.is_gateway:
            # 通过网关访问，确保路径包含服务名称前缀
            if not path.startswith("/sinocst-module-sd/"):
                # 如果路径已经以/sinocst-module-sd开头，直接返回
                # 否则添加服务名称前缀
                if path.startswith("/sinocst-module-sd"):
                    return path
                # 移除开头的斜杠（如果有），然后添加服务名称前缀
                path = path.lstrip("/")
                return f"/sinocst-module-sd/{path}"
            return path
        else:
            # 直接访问服务，移除服务名称前缀（如果有）
            if path.startswith("/sinocst-module-sd/"):
                return path.replace("/sinocst-module-sd/", "/", 1)
            elif path.startswith("/sinocst-module-sd"):
                return path.replace("/sinocst-module-sd", "", 1)
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
        
        # SD模块请求，使用配置的base_url
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
        logger.info(f"SD服务请求头（已脱敏）: {header_info}")
        
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
                        raise Exception(f"{error_msg}")
                
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
        # 路径会根据BASE_URL自动调整
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
        # 路径会根据BASE_URL自动调整
        return await self._request(
            method="GET",
            path="/sinocst-module-sd/sinocst-vbak/vbak/getVbDetail",
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
        # 路径会根据BASE_URL自动调整
        # 注意：后端期望的参数名是 vgbel，不是 vbeln
        return await self._request(
            method="GET",
            path="/sinocst-module-sd/sinocst-vbak/vbak/getVbInfoBy",
            params={"vgbel": vbeln}
        )
    
    async def check_atp_detailed(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行详细的ATP检查，返回每个物料的检查结果
        
        Args:
            order_data: 订单数据（SdKoShowVO格式）
        
        Returns:
            详细的ATP检查结果，包含每个物料的库存信息
        """
        from typing import List
        
        ps_list = order_data.get("psList", [])
        if not ps_list:
            return {
                "success": False,
                "message": "订单没有行项目数据",
                "items": []
            }
        
        # 查询每个物料的库存
        mandt = order_data.get("mandt", "600")
        mard_request_list = []
        for ps in ps_list:
            if not ps.get("matnr") or not ps.get("werks"):
                continue
            mard_request_list.append({
                "mandt": mandt,
                "matnr": ps.get("matnr"),
                "werks": ps.get("werks"),
                "lgort": ps.get("lgort")
            })
        
        if not mard_request_list:
            return {
                "success": False,
                "message": "没有有效的物料信息",
                "items": []
            }
        
        # 调用库存查询接口
        mard_result = await self._request(
            method="POST",
            path="/sinocst-module-wm/sinocst-mard/mard/getStatusById",
            json=mard_request_list
        )
        
        mard_list = mard_result.get("data", [])
        if not mard_list:
            return {
                "success": False,
                "message": "查询库存失败",
                "items": []
            }
        
        # 构建库存映射表
        # 当库存地点为空时，需要汇总该物料在该工厂下所有库存地点的库存
        mard_map = {}
        mard_map_by_matnr_werks = {}  # 用于汇总：key = matnr-werks
        
        for mard in mard_list:
            matnr = mard.get('matnr')
            werks = mard.get('werks')
            lgort = mard.get('lgort') or ''
            
            # 精确匹配的key（包含库存地点）
            key = f"{matnr}-{werks}-{lgort}"
            mard_map[key] = mard
            
            # 汇总key（不包含库存地点，用于库存地点为空时的汇总）
            summary_key = f"{matnr}-{werks}"
            if summary_key not in mard_map_by_matnr_werks:
                mard_map_by_matnr_werks[summary_key] = {
                    "labst": 0.0,
                    "speme": 0.0,
                    "lgort_list": [],
                    "maktx": mard.get("maktx") or ""
                }
            
            # 累加库存
            summary = mard_map_by_matnr_werks[summary_key]
            summary["labst"] += float(mard.get("labst") or 0)
            summary["speme"] += float(mard.get("speme") or 0)
            if lgort and lgort not in summary["lgort_list"]:
                summary["lgort_list"].append(lgort)
        
        # 查询预留库存（需要调用预留库存接口，这里先简化处理）
        # 注意：预留库存查询需要调用lips接口，暂时先返回0
        # 实际应该调用：/sinocst-master-data/lips/getReservedQty
        
        # 构建检查结果
        items = []
        all_available = True
        
        for ps in ps_list:
            matnr = ps.get("matnr")
            werks = ps.get("werks")
            lgort = ps.get("lgort")
            need_qty = float(ps.get("lfimg") or ps.get("zmeng") or 0)
            
            if not matnr or not werks:
                continue
            
            # 先尝试精确匹配（如果指定了库存地点）
            mard = None
            if lgort:
                key = f"{matnr}-{werks}-{lgort}"
                mard = mard_map.get(key)
            
            # 如果精确匹配失败，或者库存地点为空，尝试汇总所有库存地点
            if not mard:
                summary_key = f"{matnr}-{werks}"
                summary = mard_map_by_matnr_werks.get(summary_key)
                
                if summary:
                    # 使用汇总数据
                    labst = summary["labst"]
                    speme = summary["speme"]
                    available_qty = labst - speme
                    reserved_qty = 0  # 预留库存（暂时设为0）
                    actual_available_qty = available_qty - reserved_qty
                    is_available = actual_available_qty >= need_qty
                    
                    # 显示所有库存地点
                    lgort_display = ", ".join(summary["lgort_list"]) if summary["lgort_list"] else (lgort or "")
                    
                    items.append({
                        "matnr": matnr,
                        "matnr_name": summary.get("maktx") or ps.get("maktx") or "",
                        "werks": werks,
                        "lgort": lgort_display,
                        "need_qty": need_qty,
                        "labst": labst,
                        "speme": speme,
                        "available_qty": available_qty,
                        "reserved_qty": reserved_qty,
                        "actual_available_qty": actual_available_qty,
                        "is_available": is_available,
                        "message": "库存充足" if is_available else f"库存不足：需要 {need_qty}，实际可用 {actual_available_qty}"
                    })
                    
                    if not is_available:
                        all_available = False
                    continue
                else:
                    # 没有找到任何库存
                    items.append({
                        "matnr": matnr,
                        "matnr_name": ps.get("maktx") or "",
                        "werks": werks,
                        "lgort": lgort or "",
                        "need_qty": need_qty,
                        "labst": 0,  # 总库存
                        "speme": 0,  # 冻结库存
                        "available_qty": 0,  # 可用库存
                        "reserved_qty": 0,  # 预留库存
                        "actual_available_qty": 0,  # 实际可用库存
                        "is_available": False,
                        "message": f"物料 {matnr} 在工厂 {werks}{' 库存地点 ' + lgort if lgort else ''} 未维护库存"
                    })
                    all_available = False
                    continue
            
            # 精确匹配成功，使用精确数据
            labst = float(mard.get("labst") or 0)  # 总库存（非限制库存）
            speme = float(mard.get("speme") or 0)  # 冻结库存
            available_qty = labst - speme  # 可用库存
            reserved_qty = 0  # 预留库存（暂时设为0，实际应该查询）
            actual_available_qty = available_qty - reserved_qty  # 实际可用库存
            
            is_available = actual_available_qty >= need_qty
            
            items.append({
                "matnr": matnr,
                "matnr_name": mard.get("maktx") or ps.get("maktx") or "",
                "werks": werks,
                "lgort": lgort or mard.get("lgort") or "",
                "need_qty": need_qty,
                "labst": labst,
                "speme": speme,
                "available_qty": available_qty,
                "reserved_qty": reserved_qty,
                "actual_available_qty": actual_available_qty,
                "is_available": is_available,
                "message": "库存充足" if is_available else f"库存不足：需要 {need_qty}，实际可用 {actual_available_qty}"
            })
            
            if not is_available:
                all_available = False
        
        return {
            "success": all_available,
            "message": "ATP检查通过" if all_available else "ATP检查失败：部分物料库存不足",
            "items": items
        }
    
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
    
    async def get_yesterday_last_order(self) -> Optional[Dict[str, Any]]:
        """
        获取昨天的最后一个销售订单
        
        Returns:
            订单详情数据，如果不存在则返回None
        """
        from datetime import datetime, timedelta
        
        # 计算昨天的日期范围
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y%m%d")
        
        # 查询昨天的订单列表（后端默认按创建时间倒序排列，第一条就是最后一个）
        params = {
            "current": 1,
            "size": 1,
            "erdatStart": yesterday_str,
            "erdatEnd": yesterday_str
        }
        
        result = await self._request(
            method="GET",
            path="/sinocst-module-sd/sinocst-vbak/vbak/list",
            params=params
        )
        
        data = result.get("data", {})
        records = data.get("records", [])
        
        if records and len(records) > 0:
            # 获取订单详情
            vbeln = records[0].get("vbeln")
            if vbeln:
                detail_result = await self.get_order_detail(vbeln)
                return detail_result.get("data")
        
        return None
    
    async def create_sales_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建销售订单
        
        Args:
            order_data: 订单数据（VbShowVO格式）
        
        Returns:
            创建结果（包含订单号）
        """
        # 创建销售订单接口
        return await self._request(
            method="POST",
            path="/sinocst-module-sd/sinocst-vbak/vbak/saveVb",
            json=order_data
        )
    
    async def get_sales_office_by_name(self, name_keyword: str) -> Optional[Dict[str, Any]]:
        """
        根据名称关键词查找销售办事处
        
        Args:
            name_keyword: 名称关键词（如"华东"）
        
        Returns:
            销售办事处信息，如果不存在则返回None
        """
        # 获取销售办事处列表
        result = await self._request(
            method="GET",
            path="/sinocst-master-data/tvbur/page",
            params={"current": 1, "size": 100}
        )
        
        data = result.get("data", {})
        records = data.get("records", []) or data.get("data", [])
        
        # 查找名称包含关键词的销售办事处
        for office in records:
            vtext = office.get("vtext", "") or ""
            txnam_sdb = office.get("txnamSdb", "") or office.get("txnam_sdb", "") or ""
            if name_keyword in vtext or name_keyword in txnam_sdb:
                return office
        
        return None

