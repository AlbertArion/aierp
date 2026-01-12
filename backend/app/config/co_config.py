"""
CO服务配置管理
"""
import os
import base64

class COConfig:
    """CO服务配置类"""
    # CO服务基础URL（从环境变量读取）
    # 选项1：通过网关访问（支持负载均衡和服务发现）
    # BASE_URL = "http://localhost:9015"
    # 选项2：直接访问CO服务（开发调试，需要CO服务运行在对应端口，绕过网关）
    # BASE_URL = "http://localhost:9997"
    # 默认直接连接CO服务（绕过网关，更稳定）
    BASE_URL = os.getenv("CO_API_BASE_URL", "http://localhost:9997")
    
    # 强制使用直接访问模式（不通过网关）
    # 注意：如果环境变量设置了网关地址，这里会覆盖
    FORCE_DIRECT_ACCESS = os.getenv("CO_FORCE_DIRECT_ACCESS", "true").lower() == "true"
    
    # 请求超时时间（秒）
    TIMEOUT = int(os.getenv("CO_API_TIMEOUT", "30"))
    
    # 重试次数
    RETRY_COUNT = int(os.getenv("CO_API_RETRY_COUNT", "3"))
    
    # 服务间认证Token（可选，如果需要服务间认证）
    API_TOKEN = os.getenv("CO_API_TOKEN", None)
    
    # OAuth2客户端凭证（用于Basic认证，与前端保持一致）
    CLIENT_ID = os.getenv("CO_CLIENT_ID", "saber3")
    CLIENT_SECRET = os.getenv("CO_CLIENT_SECRET", "saber3_secret")
    
    @classmethod
    def get_headers(cls, additional_headers: dict = None) -> dict:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            # 添加Blade-Requested-With头（与前端保持一致）
            "Blade-Requested-With": "BladeHttpRequest"
        }
        
        # 添加Basic认证头（OAuth2客户端认证，与前端保持一致）
        # 格式：Basic base64(clientId:clientSecret)
        basic_auth = base64.b64encode(
            f"{cls.CLIENT_ID}:{cls.CLIENT_SECRET}".encode('utf-8')
        ).decode('utf-8')
        headers["Authorization"] = f"Basic {basic_auth}"
        
        # 如果配置了API Token，会通过additional_headers覆盖Authorization头
        # 但我们需要同时保留Basic认证和Bearer token，所以这里只设置Basic
        # Bearer token会通过Blade-Auth头传递
        
        # 合并额外的请求头
        if additional_headers:
            headers.update(additional_headers)
        
        return headers
