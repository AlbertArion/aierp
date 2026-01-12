"""
FI模块服务客户端
用于调用ai_erp_standard-v2507服务的FI模块接口
"""
import httpx
from httpx import HTTPStatusError, HTTPError, TimeoutException, ConnectError, RequestError
import asyncio
import logging
from typing import Dict, Any, Optional, List
from app.config.fi_config import FIConfig

logger = logging.getLogger(__name__)

class FIService:
    """FI模块服务客户端"""
    
    def __init__(self):
        self.base_url = FIConfig.BASE_URL
        self.timeout = FIConfig.TIMEOUT
        self.retry_count = FIConfig.RETRY_COUNT
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
        - 通过网关访问时，路径需要包含服务名称前缀 /sinocst-module-fa/
        - 直接访问服务时，路径不需要服务名称前缀（但FI服务似乎只支持通过网关访问）
        """
        if self.is_gateway:
            # 通过网关访问，确保路径包含服务名称前缀
            if not path.startswith("/sinocst-module-fa/"):
                if path.startswith("/sinocst-module-fa"):
                    return path
                path = path.lstrip("/")
                return f"/sinocst-module-fa/{path}"
            return path
        else:
            # 直接访问服务，移除服务名称前缀（如果有）
            # 注意：从测试来看，FI服务可能只支持通过网关访问
            # 如果直接访问失败，建议使用网关地址（http://localhost:9015）
            if path.startswith("/sinocst-module-fa/"):
                return path.replace("/sinocst-module-fa/", "/", 1)
            elif path.startswith("/sinocst-module-fa"):
                return path.replace("/sinocst-module-fa", "", 1)
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
        
        # FI模块请求，使用配置的base_url
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
        request_headers = FIConfig.get_headers(headers)
        
        # 如果设置了token，添加到请求头
        if self.token:
            token_value = self.token
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]
            elif token_value.lower().startswith("crypto "):
                pass
            
            token_value = token_value.strip()
            request_headers["Blade-Auth"] = f"bearer {token_value}"
            logger.info(f"已添加Blade-Auth头到FI服务请求 (token长度: {len(token_value)})")
        elif FIConfig.API_TOKEN:
            token_value = FIConfig.API_TOKEN
            if token_value.lower().startswith("bearer "):
                token_value = token_value[7:]
            token_value = token_value.strip()
            request_headers["Blade-Auth"] = f"bearer {token_value}"
            logger.info("使用配置的API_TOKEN")
        else:
            logger.warning("未设置token，FI服务请求可能失败")
        
        # 添加租户信息请求头
        if self.mandt:
            request_headers["X-Mandt"] = self.mandt
            logger.info(f"已添加X-Mandt头到请求: {self.mandt}")
        
        if self.tenant_id:
            request_headers["X-Tenant-Id"] = self.tenant_id
            logger.info(f"已添加X-Tenant-Id头到请求: {self.tenant_id}")
        elif self.mandt:
            request_headers["X-Tenant-Id"] = self.mandt
            logger.info(f"已添加X-Tenant-Id头到请求（使用mandt值）: {self.mandt}")
        
        # 重试逻辑（指数退避）
        last_error = None
        for attempt in range(self.retry_count):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"调用FI服务: {method} {path} (尝试 {attempt + 1}/{self.retry_count})")
                    
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json,
                        headers=request_headers
                    )
                    
                    response.raise_for_status()
                    result = response.json()
                    logger.info(f"FI服务响应成功: {path}")
                    return result
                    
            except HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code
                
                if 400 <= status_code < 500:
                    error_data = {}
                    try:
                        error_data = e.response.json()
                    except:
                        error_data = {"msg": e.response.text or "请求错误"}
                    
                    error_msg = error_data.get("msg", f"HTTP {status_code} 错误")
                    logger.error(f"FI服务请求错误: {path}, 状态码: {status_code}, 错误: {error_msg}")
                    
                    if status_code == 401:
                        raise Exception(f"FI服务认证失败: {error_msg}。请检查token是否有效、未过期，以及格式是否正确")
                    else:
                        raise Exception(f"{error_msg}")
                
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"FI服务错误，{wait_time}秒后重试: {path}, 状态码: {status_code}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"FI服务请求失败（已重试{self.retry_count}次）: {path}, 状态码: {status_code}")
                    raise Exception(f"FI服务不可用: HTTP {status_code}")
            except HTTPError as e:
                # 回退处理：如果HTTPStatusError不可用，使用HTTPError
                last_error = e
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    
                    if 400 <= status_code < 500:
                        error_data = {}
                        try:
                            error_data = e.response.json()
                        except:
                            error_data = {"msg": e.response.text or "请求错误"}
                        
                        error_msg = error_data.get("msg", f"HTTP {status_code} 错误")
                        logger.error(f"FI服务请求错误: {path}, 状态码: {status_code}, 错误: {error_msg}")
                        
                        if status_code == 401:
                            raise Exception(f"FI服务认证失败: {error_msg}。请检查token是否有效、未过期，以及格式是否正确")
                        else:
                            raise Exception(f"{error_msg}")
                    
                    if attempt < self.retry_count - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"FI服务错误，{wait_time}秒后重试: {path}, 状态码: {status_code}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"FI服务请求失败（已重试{self.retry_count}次）: {path}, 状态码: {status_code}")
                        raise Exception(f"FI服务不可用: HTTP {status_code}")
                else:
                    # 无法获取状态码，当作请求错误处理
                    if attempt < self.retry_count - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"FI服务HTTP错误，{wait_time}秒后重试: {path}")
                        await asyncio.sleep(wait_time)
                    else:
                        raise Exception(f"FI服务HTTP错误: {str(e)}")
                    
            except TimeoutException as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"FI服务请求超时，{wait_time}秒后重试: {path}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"FI服务请求超时（已重试{self.retry_count}次）: {path}")
                    raise Exception("FI服务请求超时，请稍后重试")
                    
            except ConnectError as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"无法连接到FI服务，{wait_time}秒后重试: {path}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"无法连接到FI服务（已重试{self.retry_count}次）: {path}")
                    raise Exception("无法连接到FI服务，请检查服务是否启动")
                    
            except Exception as e:
                last_error = e
                logger.error(f"FI服务请求异常: {path}, 错误: {str(e)}")
                raise Exception(f"FI服务请求失败: {str(e)}")
        
        raise Exception(f"FI服务请求失败: {str(last_error)}")
    
    # ========== 会计凭证相关方法 ==========
    
    async def create_accounting_document(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建会计凭证（录入凭证）
        
        Args:
            document_data: 凭证数据，包含凭证头信息和行项目
        
        Returns:
            创建结果（包含凭证号）
        """
        return await self._request(
            method="POST",
            path="/sinocst-module-fa/accounting-document/create",
            json=document_data
        )
    
    async def get_accounting_document_list(
        self,
        current: int = 1,
        size: int = 10,
        **filters
    ) -> Dict[str, Any]:
        """
        获取会计凭证列表
        
        Args:
            current: 当前页码
            size: 每页数量
            **filters: 其他筛选条件（如凭证号、日期范围等）
        
        Returns:
            凭证列表数据
        """
        params = {
            "current": current,
            "size": size,
            **filters
        }
        return await self._request(
            method="GET",
            path="/sinocst-module-fa/accounting-document/list",
            params=params
        )
    
    async def get_accounting_document_detail(self, belnr: str) -> Dict[str, Any]:
        """
        获取会计凭证详情
        
        Args:
            belnr: 凭证号
        
        Returns:
            凭证详情数据
        """
        return await self._request(
            method="GET",
            path="/sinocst-module-fa/accounting-document/detail",
            params={"belnr": belnr}
        )
    
    async def receive_accounting_document_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        接收会计凭证消息（用于消息接收功能）
        
        Args:
            message_data: 消息数据，包含凭证信息
        
        Returns:
            接收结果
        """
        return await self._request(
            method="POST",
            path="/sinocst-module-fa/accounting-document/message/receive",
            json=message_data
        )
    
    async def update_accounting_document(self, belnr: str, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新会计凭证
        
        Args:
            belnr: 凭证号
            document_data: 更新的凭证数据
        
        Returns:
            更新结果
        """
        return await self._request(
            method="PUT",
            path=f"/sinocst-module-fa/accounting-document/{belnr}",
            json=document_data
        )
    
    async def delete_accounting_document(self, belnr: str) -> Dict[str, Any]:
        """
        删除会计凭证
        
        Args:
            belnr: 凭证号
        
        Returns:
            删除结果
        """
        return await self._request(
            method="DELETE",
            path=f"/sinocst-module-fa/accounting-document/{belnr}"
        )
    
    # ========== FI月结流程相关方法 ==========
    
    async def execute_all_fi_closing_steps(
        self,
        company_code: str,
        fiscal_year: int,
        period: int,
        test_run: bool = True
    ) -> Dict[str, Any]:
        """
        执行所有FI月结步骤
        
        Args:
            company_code: 公司代码
            fiscal_year: 会计年度
            period: 会计期间（1-12）
            test_run: 是否试运行（默认True）
        
        Returns:
            所有步骤执行结果
        """
        return await self._request(
            method="POST",
            path="/sinocst-module-fa/period-closing-process/execute-all-steps",
            params={
                "companyCode": company_code,
                "fiscalYear": fiscal_year,
                "period": period,
                "testRun": test_run
            }
        )
    
    async def execute_fi_closing_step(
        self,
        company_code: str,
        fiscal_year: int,
        period: int,
        step_code: str,
        test_run: bool = True
    ) -> Dict[str, Any]:
        """
        执行单个FI月结步骤
        
        Args:
            company_code: 公司代码
            fiscal_year: 会计年度
            period: 会计期间（1-12）
            step_code: 步骤代码（OB52_OPEN/FBL1N/FBL3N/FBL5N/KSU5/KSV5/KO8G/AIBU/AFAB/OB52_CLOSE）
            test_run: 是否试运行（默认True）
        
        Returns:
            步骤执行结果
        """
        return await self._request(
            method="POST",
            path="/sinocst-module-fa/period-closing-process/execute-step",
            params={
                "companyCode": company_code,
                "fiscalYear": fiscal_year,
                "period": period,
                "stepCode": step_code,
                "testRun": test_run
            }
        )
    
    async def get_fi_closing_process_status(
        self,
        company_code: str,
        fiscal_year: int,
        period: int
    ) -> Dict[str, Any]:
        """
        查询FI月结流程状态
        
        Args:
            company_code: 公司代码
            fiscal_year: 会计年度
            period: 会计期间（1-12）
        
        Returns:
            月结流程状态信息
        """
        return await self._request(
            method="GET",
            path="/sinocst-module-fa/period-closing-process/process-status",
            params={
                "companyCode": company_code,
                "fiscalYear": fiscal_year,
                "period": period
            }
        )
    
    # ========== 三大报表查询相关方法 ==========
    
    async def get_balance_sheet(
        self,
        gjahr: str,
        monat: Optional[str] = None,
        bukrs: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取资产负债表
        
        Args:
            gjahr: 会计年度
            monat: 会计期间（可选，不提供则查询年度累计）
            bukrs: 公司代码（可选）
        
        Returns:
            资产负债表数据
        """
        params = {"gjahr": gjahr}
        if monat:
            params["monat"] = monat
        if bukrs:
            params["bukrs"] = bukrs
        
        return await self._request(
            method="GET",
            path="/sinocst-module-fa/report/balance-sheet",
            params=params
        )
    
    async def get_profit_loss_statement(
        self,
        gjahr: str,
        monat: Optional[str] = None,
        bukrs: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取利润表（损益表）
        
        Args:
            gjahr: 会计年度
            monat: 会计期间（可选，不提供则查询年度累计）
            bukrs: 公司代码（可选）
        
        Returns:
            利润表数据
        """
        params = {"gjahr": gjahr}
        if monat:
            params["monat"] = monat
        if bukrs:
            params["bukrs"] = bukrs
        
        return await self._request(
            method="GET",
            path="/sinocst-module-fa/report/profit-loss",
            params=params
        )
    
    async def get_cash_flow_statement(
        self,
        gjahr: str,
        monat: Optional[str] = None,
        bukrs: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取现金流量表
        
        Args:
            gjahr: 会计年度
            monat: 会计期间（可选，不提供则查询年度累计）
            bukrs: 公司代码（可选）
        
        Returns:
            现金流量表数据
        """
        params = {"gjahr": gjahr}
        if monat:
            params["monat"] = monat
        if bukrs:
            params["bukrs"] = bukrs
        
        return await self._request(
            method="GET",
            path="/sinocst-module-fa/report/cash-flow",
            params=params
        )
    
    async def get_financial_report(
        self,
        report_type: str,
        gjahr: str,
        monat: Optional[str] = None,
        bukrs: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        通用财务报表查询方法
        
        Args:
            report_type: 报表类型（balance-sheet, profit-loss, cash-flow）
            gjahr: 会计年度
            monat: 会计期间（可选）
            bukrs: 公司代码（可选）
        
        Returns:
            报表数据
        """
        params = {"gjahr": gjahr}
        if monat:
            params["monat"] = monat
        if bukrs:
            params["bukrs"] = bukrs
        
        return await self._request(
            method="GET",
            path=f"/sinocst-module-fa/report/{report_type}",
            params=params
        )
    
    # ========== 其他财务相关方法 ==========
    
    async def get_account_balance(
        self,
        saknr: str,
        gjahr: str,
        monat: Optional[str] = None,
        bukrs: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取科目余额
        
        Args:
            saknr: 科目编号
            gjahr: 会计年度
            monat: 会计期间（可选）
            bukrs: 公司代码（可选）
        
        Returns:
            科目余额数据
        """
        params = {"saknr": saknr, "gjahr": gjahr}
        if monat:
            params["monat"] = monat
        if bukrs:
            params["bukrs"] = bukrs
        
        return await self._request(
            method="GET",
            path="/sinocst-module-fa/account/balance",
            params=params
        )
    
    async def get_general_ledger(
        self,
        gjahr: str,
        monat: Optional[str] = None,
        bukrs: Optional[str] = None,
        saknr: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取总账
        
        Args:
            gjahr: 会计年度
            monat: 会计期间（可选）
            bukrs: 公司代码（可选）
            saknr: 科目编号（可选）
        
        Returns:
            总账数据
        """
        params = {"gjahr": gjahr}
        if monat:
            params["monat"] = monat
        if bukrs:
            params["bukrs"] = bukrs
        if saknr:
            params["saknr"] = saknr
        
        return await self._request(
            method="GET",
            path="/sinocst-module-fa/ledger/general",
            params=params
        )
    
    async def get_account_list(
        self,
        current: int = 1,
        size: int = 10,
        **filters
    ) -> Dict[str, Any]:
        """
        获取科目列表
        
        Args:
            current: 当前页码
            size: 每页数量
            **filters: 其他筛选条件（如科目代码、科目名称、科目类型、状态等）
        
        Returns:
            科目列表数据
        """
        params = {
            "current": current,
            "size": size,
            **filters
        }
        # 使用 /list 端点，它接受 Map<String, Object> 参数，更灵活
        return await self._request(
            method="GET",
            path="/sinocst-module-fa/gl/accounts/list",
            params=params
        )
    
    async def get_account_detail(self, account_code: str) -> Dict[str, Any]:
        """
        获取科目详情
        
        Args:
            account_code: 科目代码
        
        Returns:
            科目详情数据
        """
        return await self._request(
            method="GET",
            path="/sinocst-module-fa/gl/accounts/detail",
            params={"accountCode": account_code}
        )