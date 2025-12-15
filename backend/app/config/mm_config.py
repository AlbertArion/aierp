"""
MM模块配置
"""
import os
from typing import Dict, Optional

class MMConfig:
    """MM模块服务配置"""
    
    # MM服务基础URL（从环境变量获取，默认值）
    # 选项1：通过网关访问（支持负载均衡和服务发现）
    # BASE_URL = "http://localhost:9015"
    # 选项2：直接访问MM服务（推荐，绕过网关更稳定）
    # BASE_URL = "http://localhost:9998"
    BASE_URL = os.getenv("MM_SERVICE_BASE_URL", "http://localhost:9998")
    
    # 超时时间（秒）
    TIMEOUT = int(os.getenv("MM_SERVICE_TIMEOUT", "30"))
    
    # 重试次数
    RETRY_COUNT = int(os.getenv("MM_SERVICE_RETRY_COUNT", "3"))
    
    # API Token（可选，如果服务需要）
    API_TOKEN = os.getenv("MM_API_TOKEN", None)
    
    @staticmethod
    def get_headers(custom_headers: Optional[Dict] = None) -> Dict[str, str]:
        """
        获取请求头
        
        Args:
            custom_headers: 自定义请求头
            
        Returns:
            请求头字典
        """
        import base64
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            # 添加Blade-Requested-With头（与前端保持一致）
            "Blade-Requested-With": "BladeHttpRequest"
        }
        
        # 添加Basic认证头（OAuth2客户端认证，与前端保持一致）
        # 格式：Basic base64(clientId:clientSecret)
        client_id = os.getenv("MM_CLIENT_ID", "saber3")
        client_secret = os.getenv("MM_CLIENT_SECRET", "saber3_secret")
        basic_auth = base64.b64encode(
            f"{client_id}:{client_secret}".encode('utf-8')
        ).decode('utf-8')
        headers["Authorization"] = f"Basic {basic_auth}"
        
        # 如果配置了API Token，会通过custom_headers覆盖Authorization头
        # 但我们需要同时保留Basic认证和Bearer token，所以这里只设置Basic
        # Bearer token会通过Blade-Auth头传递（在MMService中处理）
        
        # 合并自定义请求头
        if custom_headers:
            headers.update(custom_headers)
        
        return headers

