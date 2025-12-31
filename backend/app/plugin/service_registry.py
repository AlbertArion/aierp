"""
服务注册表实现
"""
import logging
from typing import Dict, Any, Optional, Type, TypeVar

from .base import ServiceRegistry

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceRegistryImpl(ServiceRegistry):
    """服务注册表实现"""
    
    def __init__(self, app_context: Any = None):
        """
        初始化服务注册表
        
        Args:
            app_context: FastAPI应用上下文，用于获取主系统服务
        """
        self._services: Dict[str, Any] = {}
        self._app_context = app_context
    
    def register_service(self, service_name: str, service: Any) -> None:
        """注册插件服务"""
        if service_name is None or service is None:
            raise ValueError("Service name and service cannot be None")
        
        if service_name in self._services:
            logger.warning(f"Service {service_name} already registered, will be replaced")
        
        self._services[service_name] = service
        logger.info(f"Service {service_name} registered successfully")
    
    def get_service(self, service_name: str, service_type: Type[T] = None) -> Optional[T]:
        """获取插件服务"""
        service = self._services.get(service_name)
        if service is None:
            return None
        
        if service_type and not isinstance(service, service_type):
            logger.warning(f"Service {service_name} is not of type {service_type.__name__}")
            return None
        
        return service
    
    def get_system_service(self, service_type: Type[T]) -> Optional[T]:
        """获取主系统服务"""
        if self._app_context is None:
            logger.warning("App context not available")
            return None
        
        try:
            # 尝试从FastAPI应用上下文获取服务
            # 这里需要根据实际的FastAPI应用结构来实现
            # 例如：app.state.services.get(service_type)
            # 或者使用依赖注入的方式
            logger.debug(f"Getting system service: {service_type.__name__}")
            # TODO: 实现从FastAPI应用获取服务的逻辑
            return None
        except Exception as e:
            logger.debug(f"System service {service_type.__name__} not found: {e}")
            return None
    
    def unregister_service(self, service_name: str) -> None:
        """注销服务"""
        self._services.pop(service_name, None)
        logger.info(f"Service {service_name} unregistered")

