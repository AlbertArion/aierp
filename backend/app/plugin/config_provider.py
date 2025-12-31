"""
配置提供者实现
"""
import logging
from typing import Dict, Any

from .base import ConfigProvider

logger = logging.getLogger(__name__)


class ConfigProviderImpl(ConfigProvider):
    """配置提供者实现"""
    
    def __init__(self):
        """初始化配置提供者"""
        self._config_map: Dict[str, Dict[str, Any]] = {}
    
    def get_config(self, plugin_id: str) -> Dict[str, Any]:
        """读取插件配置"""
        config = self._config_map.get(plugin_id)
        if config is None:
            return {}
        return dict(config)
    
    def get_config_value(self, plugin_id: str, key: str) -> Any:
        """读取插件配置项"""
        config = self._config_map.get(plugin_id)
        if config is None:
            return None
        return config.get(key)
    
    def update_config(self, plugin_id: str, config: Dict[str, Any]) -> None:
        """更新插件配置"""
        if plugin_id is None:
            raise ValueError("Plugin ID cannot be None")
        self._config_map[plugin_id] = dict(config)
        logger.info(f"Config updated for plugin {plugin_id}")
    
    def update_config_value(self, plugin_id: str, key: str, value: Any) -> None:
        """更新插件配置项"""
        if plugin_id is None or key is None:
            raise ValueError("Plugin ID and key cannot be None")
        if plugin_id not in self._config_map:
            self._config_map[plugin_id] = {}
        self._config_map[plugin_id][key] = value
        logger.info(f"Config value updated for plugin {plugin_id}: {key} = {value}")
    
    def validate_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        """验证配置"""
        if plugin_id is None or config is None:
            return False
        # 可以扩展更复杂的验证逻辑
        return True

