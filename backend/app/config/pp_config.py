"""
PP模块配置
"""
import os
from typing import Dict, Optional

class PPConfig:
    """PP模块服务配置"""
    
    # PP服务基础URL（从环境变量获取，默认值）
    # 选项1：通过网关访问（推荐，支持负载均衡和服务发现）
    # BASE_URL = "http://localhost:9015"
    # 选项2：直接访问PP服务（开发调试，需要PP服务运行在对应端口）
    # BASE_URL = "http://localhost:8080"
    BASE_URL = os.getenv("PP_SERVICE_BASE_URL", "http://localhost:9015")
    
    # 超时时间（秒）
    TIMEOUT = int(os.getenv("PP_SERVICE_TIMEOUT", "30"))
    
    # 重试次数
    RETRY_COUNT = int(os.getenv("PP_SERVICE_RETRY_COUNT", "3"))
    
    # API Token（可选，如果服务需要）
    API_TOKEN = os.getenv("PP_API_TOKEN", None)
    
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
        client_id = os.getenv("PP_CLIENT_ID", "saber3")
        client_secret = os.getenv("PP_CLIENT_SECRET", "saber3_secret")
        basic_auth = base64.b64encode(
            f"{client_id}:{client_secret}".encode('utf-8')
        ).decode('utf-8')
        headers["Authorization"] = f"Basic {basic_auth}"
        
        # 如果配置了API Token，会通过custom_headers覆盖Authorization头
        # 但我们需要同时保留Basic认证和Bearer token，所以这里只设置Basic
        # Bearer token会通过Blade-Auth头传递（在PPService中处理）
        
        # 合并自定义请求头
        if custom_headers:
            headers.update(custom_headers)
        
        return headers

