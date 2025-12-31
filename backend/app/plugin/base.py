"""
插件基础接口和类型定义
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field


class PluginStatus(Enum):
    """插件状态枚举"""
    INSTALLED = "INSTALLED"  # 已安装
    INITIALIZED = "INITIALIZED"  # 已初始化
    STARTED = "STARTED"  # 已启动
    STOPPED = "STOPPED"  # 已停止
    ERROR = "ERROR"  # 错误状态


@dataclass
class PluginMetadata:
    """插件元数据"""
    plugin_id: str
    plugin_name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    vendor: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    api_versions: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    plugin_class: Optional[str] = None
    install_path: Optional[str] = None


class IPlugin(ABC):
    """插件接口"""
    
    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """获取插件元信息"""
        pass
    
    @abstractmethod
    def initialize(self, context: 'PluginContext') -> None:
        """初始化插件"""
        pass
    
    @abstractmethod
    def start(self) -> None:
        """启动插件"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """停止插件"""
        pass
    
    @abstractmethod
    def destroy(self) -> None:
        """销毁插件"""
        pass
    
    @abstractmethod
    def get_services(self) -> Dict[str, Any]:
        """获取插件提供的服务"""
        pass
    
    @abstractmethod
    def get_status(self) -> PluginStatus:
        """获取插件当前状态"""
        pass


class PluginContext:
    """插件上下文"""
    
    def __init__(
        self,
        app_context: Any,
        plugin_registry: 'PluginRegistry',
        service_registry: 'ServiceRegistry',
        config_provider: 'ConfigProvider',
        plugin_metadata: PluginMetadata
    ):
        self.app_context = app_context
        self.plugin_registry = plugin_registry
        self.service_registry = service_registry
        self.config_provider = config_provider
        self.plugin_metadata = plugin_metadata


class PluginRegistry(ABC):
    """插件注册表接口"""
    
    @abstractmethod
    def register(self, plugin: IPlugin) -> None:
        """注册插件"""
        pass
    
    @abstractmethod
    def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        """根据插件ID获取插件"""
        pass
    
    @abstractmethod
    def get_all_plugins(self) -> List[IPlugin]:
        """获取所有已注册的插件"""
        pass
    
    @abstractmethod
    def unregister(self, plugin_id: str) -> None:
        """注销插件"""
        pass
    
    @abstractmethod
    def check_dependencies(self, plugin_id: str) -> bool:
        """检查插件依赖是否满足"""
        pass
    
    @abstractmethod
    def get_startup_order(self) -> List[str]:
        """获取插件启动顺序"""
        pass


class ServiceRegistry(ABC):
    """服务注册表接口"""
    
    @abstractmethod
    def register_service(self, service_name: str, service: Any) -> None:
        """注册插件服务"""
        pass
    
    @abstractmethod
    def get_service(self, service_name: str, service_type: type = None) -> Any:
        """获取插件服务"""
        pass
    
    @abstractmethod
    def get_system_service(self, service_type: type) -> Any:
        """获取主系统服务"""
        pass
    
    @abstractmethod
    def unregister_service(self, service_name: str) -> None:
        """注销服务"""
        pass


class ConfigProvider(ABC):
    """配置提供者接口"""
    
    @abstractmethod
    def get_config(self, plugin_id: str) -> Dict[str, Any]:
        """读取插件配置"""
        pass
    
    @abstractmethod
    def get_config_value(self, plugin_id: str, key: str) -> Any:
        """读取插件配置项"""
        pass
    
    @abstractmethod
    def update_config(self, plugin_id: str, config: Dict[str, Any]) -> None:
        """更新插件配置"""
        pass
    
    @abstractmethod
    def update_config_value(self, plugin_id: str, key: str, value: Any) -> None:
        """更新插件配置项"""
        pass
    
    @abstractmethod
    def validate_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        """验证配置"""
        pass

