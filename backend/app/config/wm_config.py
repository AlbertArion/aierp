"""
WM模块（仓储管理）及MasterData（主数据）配置
"""
import os
import base64


class WMConfig:
    """WM模块服务配置"""

    # WM 服务基础URL
    BASE_URL = os.getenv("WM_SERVICE_BASE_URL", "http://localhost:9112")

    # MasterData 服务基础URL
    MASTER_DATA_BASE_URL = os.getenv("MASTER_DATA_BASE_URL", "http://localhost:9100")

    # 请求超时时间（秒）
    TIMEOUT = int(os.getenv("WM_SERVICE_TIMEOUT", "30"))

    # 重试次数
    RETRY_COUNT = int(os.getenv("WM_SERVICE_RETRY_COUNT", "3"))

    # OAuth2 客户端凭证
    CLIENT_ID = os.getenv("WM_CLIENT_ID", "saber3")
    CLIENT_SECRET = os.getenv("WM_CLIENT_SECRET", "saber3_secret")

    @classmethod
    def get_headers(cls, additional_headers: dict = None) -> dict:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Blade-Requested-With": "BladeHttpRequest",
        }

        basic_auth = base64.b64encode(
            f"{cls.CLIENT_ID}:{cls.CLIENT_SECRET}".encode("utf-8")
        ).decode("utf-8")
        headers["Authorization"] = f"Basic {basic_auth}"

        if additional_headers:
            headers.update(additional_headers)

        return headers
