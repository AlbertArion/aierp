"""
插件管理器
管理插件的完整生命周期
"""
import logging
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI

from .base import IPlugin, PluginContext, PluginStatus
from .loader import PluginLoader
from .registry import PluginRegistryImpl
from .service_registry import ServiceRegistryImpl
from .config_provider import ConfigProviderImpl

logger = logging.getLogger(__name__)


class PluginManager:
    """插件管理器"""
    
    def __init__(
        self,
        app: FastAPI,
        plugin_directory: Optional[str] = None,
        auto_load: bool = True
    ):
        """
        初始化插件管理器
        
        Args:
            app: FastAPI应用实例
            plugin_directory: 插件目录
            auto_load: 是否自动加载插件
        """
        self.app = app
        self.loader = PluginLoader(plugin_directory)
        self.registry = PluginRegistryImpl()
        self.service_registry = ServiceRegistryImpl(app_context=app)
        self.config_provider = ConfigProviderImpl()
        self.auto_load = auto_load
        
        if auto_load:
            self.initialize()
    
    def initialize(self) -> None:
        """初始化插件管理器，加载所有插件"""
        logger.info("Initializing plugin manager...")
        try:
            # 加载插件
            plugins = self.loader.load_plugins()
            if not plugins:
                logger.info("No plugins found to load")
                return
            
            # 注册所有插件
            for plugin in plugins:
                try:
                    self.registry.register(plugin)
                except Exception as e:
                    logger.error(f"Failed to register plugin: {plugin.get_metadata().plugin_id}", exc_info=True)
            
            # 按依赖顺序启动插件
            startup_order = self.registry.get_startup_order()
            for plugin_id in startup_order:
                try:
                    self.start_plugin(plugin_id)
                except Exception as e:
                    logger.error(f"Failed to start plugin: {plugin_id}", exc_info=True)
                    self.registry.update_status(plugin_id, PluginStatus.ERROR)
            
            logger.info(f"Plugin manager initialized successfully, {len(plugins)} plugins loaded")
        except Exception as e:
            logger.error("Failed to initialize plugin manager", exc_info=True)
    
    def shutdown(self) -> None:
        """关闭插件管理器，停止所有插件"""
        logger.info("Shutting down plugin manager...")
        plugins = self.registry.get_all_plugins()
        # 按逆序停止插件
        for plugin in reversed(plugins):
            try:
                self.stop_plugin(plugin.get_metadata().plugin_id)
            except Exception as e:
                logger.error(f"Failed to stop plugin: {plugin.get_metadata().plugin_id}", exc_info=True)
        logger.info("Plugin manager shut down completed")
    
    def start_plugin(self, plugin_id: str) -> None:
        """启动插件"""
        plugin = self.registry.get_plugin(plugin_id)
        if plugin is None:
            raise ValueError(f"Plugin not found: {plugin_id}")
        
        current_status = plugin.get_status()
        if current_status == PluginStatus.STARTED:
            logger.warning(f"Plugin {plugin_id} is already started")
            return
        
        logger.info(f"Starting plugin: {plugin_id}")
        
        try:
            # 检查依赖
            if not self.registry.check_dependencies(plugin_id):
                raise ValueError(f"Plugin dependencies not satisfied: {plugin_id}")
            
            # 如果未初始化，先初始化
            if current_status == PluginStatus.INSTALLED:
                self._initialize_plugin(plugin_id)
            
            # 创建插件上下文
            context = self._create_plugin_context(plugin.get_metadata())
            
            # 如果状态是INITIALIZED或STOPPED，需要重新初始化
            if current_status in [PluginStatus.INITIALIZED, PluginStatus.STOPPED]:
                plugin.initialize(context)
            
            # 启动插件
            plugin.start()
            self.registry.update_status(plugin_id, PluginStatus.STARTED)
            
            # 注册插件提供的服务
            self._register_plugin_services(plugin)
            
            logger.info(f"Plugin {plugin_id} started successfully")
        except Exception as e:
            self.registry.update_status(plugin_id, PluginStatus.ERROR)
            logger.error(f"Failed to start plugin: {plugin_id}", exc_info=True)
            raise
    
    def stop_plugin(self, plugin_id: str) -> None:
        """停止插件"""
        plugin = self.registry.get_plugin(plugin_id)
        if plugin is None:
            raise ValueError(f"Plugin not found: {plugin_id}")
        
        current_status = plugin.get_status()
        if current_status in [PluginStatus.STOPPED, PluginStatus.INSTALLED]:
            logger.warning(f"Plugin {plugin_id} is already stopped")
            return
        
        logger.info(f"Stopping plugin: {plugin_id}")
        
        try:
            # 注销插件提供的服务
            self._unregister_plugin_services(plugin)
            
            # 停止插件
            plugin.stop()
            self.registry.update_status(plugin_id, PluginStatus.STOPPED)
            
            logger.info(f"Plugin {plugin_id} stopped successfully")
        except Exception as e:
            self.registry.update_status(plugin_id, PluginStatus.ERROR)
            logger.error(f"Failed to stop plugin: {plugin_id}", exc_info=True)
            raise
    
    def unload_plugin(self, plugin_id: str) -> None:
        """卸载插件"""
        plugin = self.registry.get_plugin(plugin_id)
        if plugin is None:
            raise ValueError(f"Plugin not found: {plugin_id}")
        
        logger.info(f"Unloading plugin: {plugin_id}")
        
        try:
            # 先停止插件
            if plugin.get_status() == PluginStatus.STARTED:
                self.stop_plugin(plugin_id)
            
            # 销毁插件
            plugin.destroy()
            
            # 从注册表移除
            self.registry.unregister(plugin_id)
            
            logger.info(f"Plugin {plugin_id} unloaded successfully")
        except Exception as e:
            logger.error(f"Failed to unload plugin: {plugin_id}", exc_info=True)
            raise
    
    def load_plugin(self, plugin_path: str) -> None:
        """动态加载插件"""
        try:
            plugin = self.loader.load_plugin(Path(plugin_path))
            if plugin is None:
                raise ValueError(f"Failed to load plugin from {plugin_path}")
            
            self.registry.register(plugin)
            self.start_plugin(plugin.get_metadata().plugin_id)
            logger.info(f"Plugin loaded dynamically from: {plugin_path}")
        except Exception as e:
            logger.error(f"Failed to load plugin from: {plugin_path}", exc_info=True)
            raise
    
    def _initialize_plugin(self, plugin_id: str) -> None:
        """初始化插件"""
        plugin = self.registry.get_plugin(plugin_id)
        if plugin is None:
            raise ValueError(f"Plugin not found: {plugin_id}")
        
        logger.info(f"Initializing plugin: {plugin_id}")
        
        try:
            context = self._create_plugin_context(plugin.get_metadata())
            plugin.initialize(context)
            self.registry.update_status(plugin_id, PluginStatus.INITIALIZED)
            logger.info(f"Plugin {plugin_id} initialized successfully")
        except Exception as e:
            self.registry.update_status(plugin_id, PluginStatus.ERROR)
            logger.error(f"Failed to initialize plugin: {plugin_id}", exc_info=True)
            raise
    
    def _create_plugin_context(self, metadata) -> PluginContext:
        """创建插件上下文"""
        from .base import PluginContext
        return PluginContext(
            app_context=self.app,
            plugin_registry=self.registry,
            service_registry=self.service_registry,
            config_provider=self.config_provider,
            plugin_metadata=metadata
        )
    
    def _register_plugin_services(self, plugin: IPlugin) -> None:
        """注册插件提供的服务"""
        try:
            services = plugin.get_services()
            if services:
                plugin_id = plugin.get_metadata().plugin_id
                for key, service in services.items():
                    service_name = f"{plugin_id}:{key}"
                    self.service_registry.register_service(service_name, service)
        except Exception as e:
            logger.error("Failed to register plugin services", exc_info=True)
    
    def _unregister_plugin_services(self, plugin: IPlugin) -> None:
        """注销插件提供的服务"""
        try:
            services = plugin.get_services()
            if services:
                plugin_id = plugin.get_metadata().plugin_id
                for key in services.keys():
                    service_name = f"{plugin_id}:{key}"
                    self.service_registry.unregister_service(service_name)
        except Exception as e:
            logger.error("Failed to unregister plugin services", exc_info=True)

