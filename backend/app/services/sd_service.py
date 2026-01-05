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
            "sinocst-module-pp": "http://localhost:9110",
            "sinocst-module-me": "http://localhost:9999",
            "sinocst-module-co": "http://localhost:9997",  # CO模块（成本核算）
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
    
    async def get_internal_order_detail(self, aufnr: str) -> Dict[str, Any]:
        """
        获取内部订单详情
        
        Args:
            aufnr: 内部订单号（12位数字，如808000000008）
        
        Returns:
            内部订单详情数据
        """
        logger.info(f"查询内部订单详情: aufnr={aufnr}")
        # 内部订单在CO模块（sinocst-module-co）
        return await self._request(
            method="GET",
            path="/sinocst-module-co/internal-order/detail",
            params={"orderNumber": aufnr}
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
            # 如果查询库存返回空列表，说明没有库存记录
            # 返回 ATP 检查失败的结果，包含每个物料的检查信息
            items = []
            for ps in ps_list:
                matnr = ps.get("matnr")
                werks = ps.get("werks")
                lgort = ps.get("lgort")
                need_qty = float(ps.get("lfimg") or ps.get("zmeng") or 0)
                
                if not matnr or not werks:
                    continue
                
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
            
            return {
                "success": False,
                "message": "ATP检查失败：未找到物料库存记录",
                "items": items
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
                    "bound_stock": 0.0,  # 绑定订单库存
                    "free_stock": 0.0,  # 自由库存
                    "lgort_list": [],
                    "maktx": mard.get("maktx") or ""
                }
            
            # 累加库存（区分绑定订单库存和自由库存）
            summary = mard_map_by_matnr_werks[summary_key]
            sobkz = mard.get("sobkz") or ''
            vbeln_mard = mard.get("vbeln") or ''
            # 如果是绑定订单库存（sobkz='E'），累加einme
            if sobkz == 'E' and vbeln_mard:
                einme = float(mard.get("einme") or 0)
                summary["bound_stock"] += einme
            else:
                # 如果是自由库存，累加labst和speme
                summary["labst"] += float(mard.get("labst") or 0)
                summary["speme"] += float(mard.get("speme") or 0)
            if lgort and lgort not in summary["lgort_list"]:
                summary["lgort_list"].append(lgort)
        
        # 获取当前销售订单号（用于排除当前订单的预留库存）
        vbeln = order_data.get("vbeln", "")
        
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
                    # 区分绑定订单库存和自由库存
                    bound_stock_qty = summary.get("bound_stock", 0.0)  # 绑定订单库存数量
                    labst = summary["labst"]
                    speme = summary["speme"]
                    # 修复：冻结库存不应该是负数，如果为负数，说明数据异常
                    if speme < 0:
                        if labst == 0:
                            labst = abs(speme)
                            speme = 0
                        else:
                            speme = 0
                    free_stock_qty = labst - speme  # 自由库存数量
                    
                    available_qty = bound_stock_qty + free_stock_qty
                    
                    # 预留库存：只从自由库存扣除，排除当前销售订单的预留
                    # 注意：对于绑定销售订单的库存，不需要减去预留库存，因为绑定订单库存是专门为该订单预留的
                    # 只有自由库存才需要减去其他交货单的预留库存
                    reserved_qty = 0.0
                    if free_stock_qty > 0:
                        try:
                            reserved_result = await self._request(
                                method="GET",
                                path="/sinocst-master-data/sinocst-lips/lips/getReservedQty",
                                params={
                                    "mandt": mandt,
                                    "matnr": matnr,
                                    "werks": werks,
                                    "lgort": lgort or "",
                                    "excludeVbeln": "",  # ATP检查时，交货单还未创建
                                    "excludeVgbel": vbeln or ""  # 排除当前销售订单的预留
                                }
                            )
                            reserved_qty = float(reserved_result.get("data", 0) or 0)
                        except Exception as e:
                            # 如果查询预留库存失败，设为0，不影响ATP检查
                            reserved_qty = 0
                        # 预留库存不能超过自由库存数量
                        if reserved_qty > free_stock_qty:
                            reserved_qty = free_stock_qty
                    
                    # 计算实际可用库存 = 绑定订单库存 + 自由库存 - 其他交货单的预留库存
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
                        "labst": labst,  # 总库存（用于显示）
                        "speme": speme,  # 冻结库存（用于显示）
                        "available_qty": available_qty,  # 总可用库存（绑定订单库存 + 自由库存）
                        "reserved_qty": reserved_qty,  # 预留库存
                        "actual_available_qty": actual_available_qty,  # 实际可用库存
                        "is_available": is_available,
                        "message": f"库存充足（总库存 {available_qty}，预留 {reserved_qty}，实际可用 {actual_available_qty}）" if is_available else f"库存不足：需要 {need_qty}，总库存 {available_qty}，预留 {reserved_qty}，实际可用 {actual_available_qty}"
                    })
                    
                    if not is_available:
                        all_available = False
                    continue
                else:
                    # 没有找到任何库存
                    # 如果订单行项目的库存地点为空，显示"所有库存地点"
                    lgort_display = lgort if lgort else "所有库存地点"
                    items.append({
                        "matnr": matnr,
                        "matnr_name": ps.get("maktx") or "",
                        "werks": werks,
                        "lgort": lgort_display,
                        "need_qty": need_qty,
                        "labst": 0,  # 总库存
                        "speme": 0,  # 冻结库存
                        "available_qty": 0,  # 可用库存
                        "reserved_qty": 0,  # 预留库存
                        "actual_available_qty": 0,  # 实际可用库存
                        "is_available": False,
                        "message": f"物料 {matnr} 在工厂 {werks}{' 库存地点 ' + lgort if lgort else ' 所有库存地点'} 未维护库存"
                    })
                    all_available = False
                    continue
            
            # 精确匹配成功，使用精确数据
            # 区分绑定订单库存和自由库存
            sobkz = mard.get("sobkz") or ''
            vbeln_mard = mard.get("vbeln") or ''
            bound_stock_qty = 0.0  # 绑定订单库存数量
            free_stock_qty = 0.0  # 自由库存数量
            
            # 如果是绑定订单库存（sobkz='E'），使用einme
            if sobkz == 'E' and vbeln_mard:
                einme = float(mard.get("einme") or 0)
                bound_stock_qty = einme
            else:
                # 如果是自由库存，使用labst - speme
                labst = float(mard.get("labst") or 0)
                speme = float(mard.get("speme") or 0)
                # 修复：冻结库存不应该是负数，如果为负数，说明数据异常
                if speme < 0:
                    if labst == 0:
                        labst = abs(speme)
                        speme = 0
                    else:
                        speme = 0
                free_stock_qty = labst - speme
            
            available_qty = bound_stock_qty + free_stock_qty
            
            # 预留库存：只从自由库存扣除，排除当前销售订单的预留
            # 注意：对于绑定销售订单的库存，不需要减去预留库存，因为绑定订单库存是专门为该订单预留的
            # 只有自由库存才需要减去其他交货单的预留库存
            reserved_qty = 0.0
            if free_stock_qty > 0:
                try:
                    reserved_result = await self._request(
                        method="GET",
                        path="/sinocst-master-data/sinocst-lips/lips/getReservedQty",
                        params={
                            "mandt": mandt,
                            "matnr": matnr,
                            "werks": werks,
                            "lgort": lgort or "",
                            "excludeVbeln": "",  # ATP检查时，交货单还未创建
                            "excludeVgbel": vbeln or ""  # 排除当前销售订单的预留
                        }
                    )
                    reserved_qty = float(reserved_result.get("data", 0) or 0)
                except Exception as e:
                    # 如果查询预留库存失败，设为0，不影响ATP检查
                    reserved_qty = 0
                # 预留库存不能超过自由库存数量
                if reserved_qty > free_stock_qty:
                    reserved_qty = free_stock_qty
            
            # 计算实际可用库存 = 绑定订单库存 + 自由库存 - 其他交货单的预留库存
            actual_available_qty = available_qty - reserved_qty
            
            is_available = actual_available_qty >= need_qty
            
            # 获取labst和speme用于显示（如果是绑定订单库存，labst可能为0）
            labst_display = float(mard.get("labst") or 0) if sobkz != 'E' else 0
            speme_display = float(mard.get("speme") or 0) if sobkz != 'E' else 0
            if sobkz == 'E':
                # 绑定订单库存，使用einme作为labst显示
                labst_display = float(mard.get("einme") or 0)
            
            items.append({
                "matnr": matnr,
                "matnr_name": mard.get("maktx") or ps.get("maktx") or "",
                "werks": werks,
                "lgort": lgort or mard.get("lgort") or "",
                "need_qty": need_qty,
                "labst": labst_display,  # 总库存（用于显示）
                "speme": speme_display,  # 冻结库存（用于显示）
                "available_qty": available_qty,  # 总可用库存（绑定订单库存 + 自由库存）
                "reserved_qty": reserved_qty,  # 预留库存
                "actual_available_qty": actual_available_qty,  # 实际可用库存
                "is_available": is_available,
                "message": f"库存充足（总库存 {available_qty}，预留 {reserved_qty}，实际可用 {actual_available_qty}）" if is_available else f"库存不足：需要 {need_qty}，总库存 {available_qty}，预留 {reserved_qty}，实际可用 {actual_available_qty}"
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
    
    async def get_latest_order(self) -> Optional[Dict[str, Any]]:
        """
        获取最新的销售订单（按创建时间倒序，第一条）
        
        Returns:
            订单详情数据，如果不存在则返回None
        """
        # 查询订单列表（后端默认按创建时间倒序排列，第一条就是最新的）
        params = {
            "current": 1,
            "size": 1
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
                detail_data = detail_result.get("data")
                # 检查返回的数据类型：如果是列表，取第一个元素；如果是字典，直接使用
                if isinstance(detail_data, list):
                    if len(detail_data) > 0:
                        return detail_data[0]
                    else:
                        return None
                elif isinstance(detail_data, dict):
                    return detail_data
                else:
                    return None
        
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
    
    async def get_sales_group_by_name(self, name_keyword: str) -> Optional[Dict[str, Any]]:
        """
        根据名称关键词查找销售组
        
        Args:
            name_keyword: 名称关键词（如"经销商销售组"）
        
        Returns:
            销售组信息，如果不存在则返回None
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # 获取销售组列表
        result = await self._request(
            method="GET",
            path="/sinocst-master-data/tvkgr/list",
            params={}
        )
        
        data = result.get("data", {})
        records = data.get("records", []) or data.get("data", [])
        
        if not records:
            logger.warning(f"未获取到销售组列表")
            return None
        
        # 规范化关键词（去除空格，转为小写用于匹配）
        keyword_normalized = name_keyword.strip().lower()
        # 移除常见的后缀词，提高匹配灵活性
        keyword_clean = keyword_normalized.replace("销售组", "").replace("组", "").strip()
        
        # 优先匹配：完全匹配（忽略大小写和空格）
        for group in records:
            bezei = (group.get("bezei", "") or "").strip()
            vkgrp = (group.get("vkgrp", "") or "").strip()
            bezei_lower = bezei.lower()
            vkgrp_lower = vkgrp.lower()
            
            # 完全匹配（忽略大小写）
            if bezei_lower == keyword_normalized or vkgrp_lower == keyword_normalized:
                logger.info(f"找到完全匹配的销售组: {vkgrp} - {bezei}")
                return group
        
        # 次优匹配：包含匹配（忽略大小写）
        for group in records:
            bezei = (group.get("bezei", "") or "").strip()
            vkgrp = (group.get("vkgrp", "") or "").strip()
            bezei_lower = bezei.lower()
            vkgrp_lower = vkgrp.lower()
            
            # 包含匹配（忽略大小写）
            if keyword_normalized in bezei_lower or keyword_normalized in vkgrp_lower:
                logger.info(f"找到包含匹配的销售组: {vkgrp} - {bezei}")
                return group
        
        # 第三优先级：如果关键词包含"销售组"等后缀，尝试去掉后缀后匹配
        if keyword_clean and keyword_clean != keyword_normalized:
            for group in records:
                bezei = (group.get("bezei", "") or "").strip()
                vkgrp = (group.get("vkgrp", "") or "").strip()
                bezei_clean = bezei.lower().replace("销售组", "").replace("组", "").strip()
                vkgrp_clean = vkgrp.lower().replace("销售组", "").replace("组", "").strip()
                
                # 清理后的匹配
                if (keyword_clean in bezei_clean or keyword_clean in vkgrp_clean or 
                    bezei_clean in keyword_clean or vkgrp_clean in keyword_clean):
                    logger.info(f"找到清理后匹配的销售组: {vkgrp} - {bezei} (关键词: {keyword_clean})")
                return group
        
        # 如果都没匹配到，记录所有销售组信息用于调试
        logger.warning(f"未找到包含'{name_keyword}'的销售组。可用销售组列表:")
        for group in records[:10]:  # 只记录前10个，避免日志过长
            bezei = (group.get("bezei", "") or "").strip()
            vkgrp = (group.get("vkgrp", "") or "").strip()
            logger.warning(f"  - {vkgrp}: {bezei}")
        
        return None
    
    async def post_delivery(self, vbeln: str) -> Dict[str, Any]:
        """
        交货单过账
        
        Args:
            vbeln: 交货单号
        
        Returns:
            过账结果
        """
        return await self._request(
            method="POST",
            path="/sinocst-master-data/likp/sd/postShipment",
            json={"vbeln": vbeln}
        )
    
    async def create_invoice_from_delivery(self, delivery_vbeln: str) -> Dict[str, Any]:
        """
        从交货单创建发票
        
        Args:
            delivery_vbeln: 交货单号
        
        Returns:
            创建发票结果（包含发票号）
        """
        # 先获取交货单详情
        delivery_detail = await self._request(
            method="GET",
            path="/sinocst-master-data/likp/sd/detail",
            params={"vbeln": delivery_vbeln}
        )
        
        if delivery_detail.get("code") != 200:
            raise Exception(f"获取交货单详情失败：{delivery_detail.get('msg', '未知错误')}")
        
        delivery_data = delivery_detail.get("data")
        if not delivery_data:
            raise Exception("交货单不存在或无法获取交货单信息")
        
        # 构建创建发票的请求数据
        invoice_data = {
            "sourceType": "DELIVERY",
            "sourceVbelnList": [delivery_vbeln],  # 必须是数组格式
            "fkdty": "F2",  # 标准开票
            "fkdat": "",  # 开票日期，由后端自动设置
            "prsdt": "",  # 定价日期，由后端自动设置
        }
        
        # 调用创建发票接口
        return await self._request(
            method="POST",
            path="/sinocst-module-sd/invoice/create",
            json=invoice_data
        )
    
    async def get_production_order_detail(self, aufnr: str) -> Dict[str, Any]:
        """
        获取生产订单详情
        
        Args:
            aufnr: 生产订单号
        
        Returns:
            生产订单详情（包含resbList等）
        """
        return await self._request(
            method="GET",
            path="/sinocst-module-pp/productOrder/detail",
            params={"aufnr": aufnr}
        )
    
    async def check_production_order_material_availability(self, aufnr: str) -> Dict[str, Any]:
        """
        检查生产订单物料可用性（齐套性检查）
        
        Args:
            aufnr: 生产订单号
        
        Returns:
            齐套检查结果
        """
        # 先获取生产订单详情（包含BOM组件resbList）
        try:
            detail_result = await self.get_production_order_detail(aufnr)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"获取生产订单详情失败: {error_msg}", exc_info=True)
            raise Exception(f"获取生产订单 {aufnr} 详情失败：{error_msg}")
        
        if detail_result.get("code") != 200:
            error_msg = detail_result.get("msg", "未知错误")
            logger.error(f"获取生产订单详情返回错误: code={detail_result.get('code')}, msg={error_msg}")
            raise Exception(f"获取生产订单详情失败：{error_msg}")
        
        order_data = detail_result.get("data")
        if not order_data:
            raise Exception(f"生产订单 {aufnr} 不存在或无法获取订单信息")
        
        # 获取BOM组件列表（resbList）
        resb_list = order_data.get("resbList", [])
        if not resb_list:
            # 获取订单信息用于错误提示
            matnr = order_data.get("matnr", "未知")
            werks = order_data.get("werks", "未知")
            stlan = order_data.get("stlan", "未配置")
            stlal = order_data.get("stlal", "未配置")
            rsnum = order_data.get("rsnum", "未知")
            
            logger.warning(f"生产订单 {aufnr} 没有BOM组件数据（resbList为空）。订单信息：物料={matnr}, 工厂={werks}, BOM用途={stlan}, BOM备选={stlal}, 预留号={rsnum}")
            return {
                "code": 400,  # 改为400，表示请求错误（无法检查）
                "success": False,
                "data": [],
                "message": f"生产订单 {aufnr} 没有BOM组件数据，无法进行物料可用性检查。物料：{matnr}，工厂：{werks}。请检查物料在工厂下是否配置了BOM（用途：{stlan}，备选：{stlal}）。",
                "error_type": "NO_BOM_DATA"  # 添加错误类型标识
            }
        
        # 获取生产订单数量（gamng：总订单数量）
        # 如果gamng为空，尝试其他可能的字段名
        order_quantity = order_data.get("gamng") or order_data.get("gmenge") or order_data.get("zmeng") or 0
        try:
            order_quantity = float(order_quantity) if order_quantity else 0
        except (ValueError, TypeError):
            order_quantity = 0
        
        # 如果订单数量为0或未找到，记录警告但继续处理（使用bdmng的原始值）
        if order_quantity == 0:
            logger.warning(f"生产订单 {aufnr} 的订单数量（gamng/gmenge/zmeng）为0或未找到，将使用BOM组件原始数量")
        
        # 将resbList转换为mareqItem格式（用于齐套检查）
        mareq_items = []
        for resb in resb_list:
            # 跳过没有物料号或需求数量为0的组件
            matnr = resb.get("matnr")
            # resb中的bdmng是每个单位父物料所需的组件数量
            bdmng_per_unit = resb.get("bdmng") or resb.get("erfmg") or 0
            if not matnr or bdmng_per_unit == 0:
                continue
            
            # 计算总需求数量 = 每个单位所需数量 × 生产订单数量
            # 如果订单数量为0，使用原始的bdmng_per_unit（向后兼容）
            if order_quantity > 0:
                total_required_qty = float(bdmng_per_unit) * order_quantity
            else:
                total_required_qty = float(bdmng_per_unit)
            
            # resb的字段：matnr, werks, lgort, bdmng（每个单位的需求数量）, erfme（单位）等
            # mareqItem需要的字段：matnr, werks, lgort, plmng（计划领料数，使用总需求数量）, bdmng等
            # 注意：不包含mandt字段，mandt将从请求头X-Mandt获取
            mareq_item = {
                "matnr": matnr,
                "werks": resb.get("werks") or order_data.get("werks"),
                "lgort": resb.get("lgort") or order_data.get("lgort"),
                "plmng": total_required_qty,  # 计划领料数使用总需求数量（每个单位数量 × 订单数量）
                "bdmng": total_required_qty,  # 需求数量（总需求数量）
                "erfme": resb.get("erfme") or resb.get("meins"),  # 单位
                "maktx": resb.get("maktx"),  # 物料描述
                "rsnum": resb.get("rsnum"),  # 预留号
                "rspos": resb.get("rspos"),  # 预留项目号
                "relatnr": aufnr  # 关联订单号（生产订单号）
                # 不包含mandt字段，mandt将从请求头X-Mandt获取，避免传递错误的mandt值
            }
            # 只添加有效的mareq_item（必须有物料号和工厂）
            if mareq_item.get("matnr") and mareq_item.get("werks"):
                mareq_items.append(mareq_item)
        
        # 调用齐套检查API
        try:
            check_result = await self._request(
                method="POST",
                path="/sinocst-module-me/sinocst-mareqHeader/mareqItem/checkBatch",
                json=mareq_items
            )
            # 在返回结果中添加order_info，包含resb_list和mareq_items，以便后续补充字段
            if isinstance(check_result, dict):
                check_result["order_info"] = {
                    "aufnr": aufnr,
                    "resb_list": resb_list,
                    "mareq_items": mareq_items,
                    "order_quantity": order_quantity  # 添加订单数量，以便后续计算时使用
                }
            return check_result
        except Exception as e:
            error_msg = str(e)
            # 如果是连接错误，返回友好的提示信息，而不是抛出异常
            if "无法连接到SD服务" in error_msg or "ConnectError" in error_msg or "connection" in error_msg.lower():
                logger.warning(f"物料可用性检查服务不可用: {error_msg}")
                return {
                    "code": 503,  # 503 Service Unavailable
                    "success": False,
                    "data": [],
                    "message": f"物料可用性检查服务暂时不可用（sinocst-module-me服务未启动或无法连接）。生产订单 {aufnr} 的BOM组件信息已获取，但无法进行可用性检查。请确保物料需求管理服务（sinocst-module-me）已启动并运行在端口9999。",
                    "error_type": "SERVICE_UNAVAILABLE",
                    "order_info": {
                        "aufnr": aufnr,
                        "resb_count": len(resb_list),
                        "mareq_items_count": len(mareq_items),
                        "resb_list": resb_list,  # 提供BOM组件信息，即使无法检查可用性
                        "order_quantity": order_quantity  # 添加订单数量
                    }
                }
            else:
                # 其他错误继续抛出
                raise
    
    async def check_internal_order_material_availability(self, aufnr: str) -> Dict[str, Any]:
        """
        检查内部订单物料可用性（齐套性检查）
        
        Args:
            aufnr: 内部订单号（12位数字，如808000000008）
        
        Returns:
            齐套检查结果
        """
        # 先获取内部订单详情
        try:
            detail_result = await self.get_internal_order_detail(aufnr)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"获取内部订单详情失败: {error_msg}", exc_info=True)
            raise Exception(f"获取内部订单 {aufnr} 详情失败：{error_msg}")
        
        if detail_result.get("code") != 200:
            error_msg = detail_result.get("msg", "未知错误")
            logger.error(f"获取内部订单详情返回错误: code={detail_result.get('code')}, msg={error_msg}")
            raise Exception(f"获取内部订单详情失败：{error_msg}")
        
        order_data = detail_result.get("data")
        if not order_data:
            raise Exception(f"内部订单 {aufnr} 不存在或无法获取订单信息")
        
        # 获取物料号和工厂
        matnr = order_data.get("materialNumber") or order_data.get("matnr")
        werks = order_data.get("plant") or order_data.get("werks")
        
        if not matnr:
            raise Exception(f"内部订单 {aufnr} 未关联物料，无法进行齐套性检查")
        if not werks:
            raise Exception(f"内部订单 {aufnr} 未设置工厂，无法进行齐套性检查")
        
        # 获取内部订单数量（从销售订单行项目获取）
        order_quantity = order_data.get("orderQuantity") or order_data.get("gamng") or order_data.get("menge") or 1
        try:
            order_quantity = float(order_quantity) if order_quantity else 1
        except (ValueError, TypeError):
            order_quantity = 1
        
        # 调用BOM展开接口获取BOM组件列表
        try:
            bom_result = await self._request(
                method="GET",
                path=f"/sinocst-module-co/internal-order/{aufnr}/bom-list",
                params={}
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"获取内部订单BOM列表失败: {error_msg}", exc_info=True)
            raise Exception(f"获取内部订单 {aufnr} BOM列表失败：{error_msg}")
        
        if bom_result.get("code") != 200:
            error_msg = bom_result.get("msg", "未知错误")
            logger.error(f"获取内部订单BOM列表返回错误: code={bom_result.get('code')}, msg={error_msg}")
            raise Exception(f"获取内部订单BOM列表失败：{error_msg}")
        
        bom_list = bom_result.get("data") or []
        # 如果BOM列表为空，尝试自动执行BOM展开
        if not bom_list:
            logger.info(f"内部订单 {aufnr} BOM列表为空，尝试自动执行BOM展开")
            try:
                # 调用BOM展开接口（POST方法）
                bom_explode_result = await self._request(
                    method="POST",
                    path=f"/sinocst-module-co/internal-order/{aufnr}/bom-explode",
                    json={}
                )
                
                if bom_explode_result.get("code") == 200:
                    bom_tree = bom_explode_result.get("data") or []
                    if bom_tree:
                        logger.info(f"内部订单 {aufnr} BOM展开成功，BOM树节点数: {len(bom_tree)}")
                        # 调试：检查BOM树结构
                        if bom_tree:
                            first_node = bom_tree[0]
                            logger.info(f"BOM树第一个节点: matnr={first_node.get('matnr')}, children数量={len(first_node.get('children', []))}")
                        # 将BOM树形结构转换为列表格式
                        bom_list = self._flatten_bom_tree_to_list(bom_tree)
                        logger.info(f"内部订单 {aufnr} BOM树转换完成，共 {len(bom_list)} 个组件")
                
                # 如果BOM展开后仍然为空，检查是否是物料没有配置BOM
                if not bom_list:
                    logger.warning(f"内部订单 {aufnr} BOM展开后仍然没有组件数据")
                    # 检查物料是否配置了BOM
                    if not matnr:
                        return {
                            "code": 400,
                            "success": False,
                            "data": [],
                            "message": f"内部订单 {aufnr} 未关联物料，无法进行齐套性检查。请先为内部订单关联物料。",
                            "error_type": "NO_MATERIAL"
                        }
                    else:
                        return {
                            "code": 400,
                            "success": False,
                            "data": [],
                            "message": f"物料 {matnr} 在工厂 {werks} 下未配置BOM或BOM中没有组件物料，无法进行齐套性检查。请检查物料主数据中的BOM配置。",
                            "error_type": "NO_BOM_DATA"
                        }
            except Exception as e:
                error_msg = str(e)
                logger.error(f"自动执行BOM展开失败: {error_msg}", exc_info=True)
                # 如果自动展开失败，返回友好的错误信息
                if not matnr:
                    return {
                        "code": 400,
                        "success": False,
                        "data": [],
                        "message": f"内部订单 {aufnr} 未关联物料，无法进行齐套性检查。请先为内部订单关联物料。",
                        "error_type": "NO_MATERIAL"
                    }
                else:
                    return {
                        "code": 400,
                        "success": False,
                        "data": [],
                        "message": f"内部订单 {aufnr} 没有BOM组件数据，无法进行物料可用性检查。BOM展开失败：{error_msg}。请检查物料 {matnr} 在工厂 {werks} 下的BOM配置。",
                        "error_type": "NO_BOM_DATA"
                    }
        
        # 将BOM列表转换为mareqItem格式（用于齐套检查）
        mareq_items = []
        for bom_item in bom_list:
            # 跳过没有物料号或需求数量为0的组件
            component_matnr = bom_item.get("idnrk") or bom_item.get("matnr")
            menge = bom_item.get("menge") or bom_item.get("bdmng") or 0
            
            if not component_matnr or menge == 0:
                continue
            
            # 计算总需求数量 = BOM中的数量 × 内部订单数量
            try:
                total_required_qty = float(menge) * order_quantity
            except (ValueError, TypeError):
                total_required_qty = float(menge)
            
            # 构建mareqItem
            mareq_item = {
                "matnr": component_matnr,
                "werks": bom_item.get("werks") or werks,
                "lgort": bom_item.get("lgort") or "",
                "plmng": total_required_qty,  # 计划领料数
                "bdmng": total_required_qty,  # 需求数量
                "erfme": bom_item.get("meins") or bom_item.get("erfme"),  # 单位
                "maktx": bom_item.get("ojtxp") or bom_item.get("maktx"),  # 物料描述
                "relatnr": aufnr  # 关联订单号（内部订单号）
            }
            # 只添加有效的mareq_item（必须有物料号和工厂）
            if mareq_item.get("matnr") and mareq_item.get("werks"):
                mareq_items.append(mareq_item)
        
        if not mareq_items:
            logger.warning(f"内部订单 {aufnr} 没有有效的BOM组件数据")
            return {
                "code": 400,
                "success": False,
                "data": [],
                "message": "内部订单没有有效的BOM组件数据，无法进行物料可用性检查",
                "error_type": "NO_VALID_BOM_DATA"
            }
        
        # 调用齐套检查API
        try:
            check_result = await self._request(
                method="POST",
                path="/sinocst-module-me/sinocst-mareqHeader/mareqItem/checkBatch",
                json=mareq_items
            )
            # 在返回结果中添加order_info
            if isinstance(check_result, dict):
                check_result["order_info"] = {
                    "aufnr": aufnr,
                    "bom_list": bom_list,
                    "mareq_items": mareq_items,
                    "order_quantity": order_quantity
                }
            return check_result
        except Exception as e:
            error_msg = str(e)
            # 如果是连接错误，返回友好的提示信息
            if "无法连接到" in error_msg or "ConnectError" in error_msg or "connection" in error_msg.lower():
                logger.warning(f"内部订单物料可用性检查服务不可用: {error_msg}")
                return {
                    "code": 503,
                    "success": False,
                    "data": [],
                    "message": f"物料可用性检查服务暂时不可用（sinocst-module-me服务未启动或无法连接）。内部订单 {aufnr} 的BOM组件信息已获取，但无法进行可用性检查。请确保物料需求管理服务（sinocst-module-me）已启动并运行在端口9999。",
                    "error_type": "SERVICE_UNAVAILABLE",
                    "order_info": {
                        "aufnr": aufnr,
                        "bom_count": len(bom_list),
                        "mareq_items_count": len(mareq_items),
                        "bom_list": bom_list,
                        "order_quantity": order_quantity
                    }
                }
            else:
                # 其他错误继续抛出
                raise
    
    def _flatten_bom_tree_to_list(self, bom_tree: list, result: list = None) -> list:
        """
        将BOM树形结构转换为列表格式
        
        Args:
            bom_tree: BOM树形结构（BomTreeDTO列表，根节点包含父物料，children包含组件）
            result: 结果列表（递归使用）
        
        Returns:
            BOM列表格式（BomListDTO列表）
        """
        if result is None:
            result = []
        
        if not isinstance(bom_tree, list):
            return result
        
        for node in bom_tree:
            # 处理有idnrk的组件节点（BomChildrenDTO）
            # 注意：根节点（BomTreeDTO）可能没有idnrk，只有children
            node_idnrk = node.get("idnrk")
            if node_idnrk:
                bom_item = {
                    "idnrk": node.get("idnrk"),
                    "matnr": node.get("idnrk"),  # 兼容字段
                    "ojtxp": node.get("idnrkMaktx") or node.get("idnrkMatkx") or node.get("potx1") or node.get("maktx") or "",
                    "maktx": node.get("idnrkMaktx") or node.get("idnrkMatkx") or node.get("potx1") or node.get("maktx") or "",
                    "menge": node.get("menge") or node.get("bdmng") or 0,
                    "bdmng": node.get("menge") or node.get("bdmng") or 0,
                    "meins": node.get("meins") or node.get("erfme") or "",
                    "erfme": node.get("meins") or node.get("erfme") or "",
                    "werks": node.get("pswrk") or node.get("werks") or "",
                    "lgort": node.get("lgort") or "",
                    "stufe": node.get("stufe") or "1"
                }
                result.append(bom_item)
            
            # 递归处理子节点（无论是根节点的children还是子节点的children）
            children = node.get("children")
            if children and isinstance(children, list) and len(children) > 0:
                self._flatten_bom_tree_to_list(children, result)
        
        return result

