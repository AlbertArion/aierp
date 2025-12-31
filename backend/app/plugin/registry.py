"""
插件注册表实现
"""
import logging
from typing import Dict, List, Optional
from collections import defaultdict, deque

from .base import IPlugin, PluginMetadata, PluginStatus, PluginRegistry

logger = logging.getLogger(__name__)


class PluginRegistryImpl(PluginRegistry):
    """插件注册表实现"""
    
    def __init__(self):
        """初始化注册表"""
        self._plugins: Dict[str, IPlugin] = {}
        self._metadata: Dict[str, PluginMetadata] = {}
        self._status: Dict[str, PluginStatus] = {}
        self._dependency_graph: Dict[str, List[str]] = {}
    
    def register(self, plugin: IPlugin) -> None:
        """注册插件"""
        if plugin is None:
            raise ValueError("Plugin cannot be None")
        
        metadata = plugin.get_metadata()
        if metadata is None or metadata.plugin_id is None:
            raise ValueError("Plugin metadata and plugin_id cannot be None")
        
        plugin_id = metadata.plugin_id
        if plugin_id in self._plugins:
            logger.warning(f"Plugin {plugin_id} already registered, will be replaced")
        
        self._plugins[plugin_id] = plugin
        self._metadata[plugin_id] = metadata
        self._status[plugin_id] = PluginStatus.INSTALLED
        
        # 构建依赖关系图
        if metadata.dependencies:
            self._dependency_graph[plugin_id] = list(metadata.dependencies)
        else:
            self._dependency_graph[plugin_id] = []
        
        logger.info(f"Plugin {plugin_id} registered successfully")
    
    def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        """根据插件ID获取插件"""
        return self._plugins.get(plugin_id)
    
    def get_all_plugins(self) -> List[IPlugin]:
        """获取所有已注册的插件"""
        return list(self._plugins.values())
    
    def unregister(self, plugin_id: str) -> None:
        """注销插件"""
        self._plugins.pop(plugin_id, None)
        self._metadata.pop(plugin_id, None)
        self._status.pop(plugin_id, None)
        self._dependency_graph.pop(plugin_id, None)
        logger.info(f"Plugin {plugin_id} unregistered")
    
    def check_dependencies(self, plugin_id: str) -> bool:
        """检查插件依赖是否满足"""
        metadata = self._metadata.get(plugin_id)
        if metadata is None:
            return False
        
        dependencies = metadata.dependencies
        if not dependencies:
            return True
        
        for dependency in dependencies:
            # 解析依赖格式：plugin_id:version 或 plugin_id
            dep_plugin_id = dependency.split(":")[0].strip()
            if dep_plugin_id not in self._plugins:
                logger.warning(f"Plugin {plugin_id} dependency {dep_plugin_id} not found")
                return False
        
        return True
    
    def get_startup_order(self) -> List[str]:
        """
        获取插件启动顺序（拓扑排序）
        
        Returns:
            插件ID列表，按启动顺序排列
        """
        result = []
        in_degree = defaultdict(int)
        graph = defaultdict(list)
        
        # 初始化入度和图
        for plugin_id in self._plugins.keys():
            in_degree[plugin_id] = 0
            graph[plugin_id] = []
        
        # 构建图：A依赖B，则B -> A
        for plugin_id, dependencies in self._dependency_graph.items():
            for dependency in dependencies:
                dep_plugin_id = dependency.split(":")[0].strip()
                if dep_plugin_id in graph:
                    graph[dep_plugin_id].append(plugin_id)
                    in_degree[plugin_id] += 1
        
        # 拓扑排序
        queue = deque()
        for plugin_id, degree in in_degree.items():
            if degree == 0:
                queue.append(plugin_id)
        
        while queue:
            plugin_id = queue.popleft()
            result.append(plugin_id)
            
            for dependent in graph[plugin_id]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # 检查是否有循环依赖
        if len(result) != len(self._plugins):
            logger.error("Circular dependency detected in plugins")
            raise ValueError("Circular dependency detected in plugins")
        
        return result
    
    def get_metadata(self, plugin_id: str) -> Optional[PluginMetadata]:
        """获取插件元数据"""
        return self._metadata.get(plugin_id)
    
    def update_status(self, plugin_id: str, status: PluginStatus) -> None:
        """更新插件状态"""
        self._status[plugin_id] = status
    
    def get_status(self, plugin_id: str) -> Optional[PluginStatus]:
        """获取插件状态"""
        return self._status.get(plugin_id, PluginStatus.INSTALLED)

