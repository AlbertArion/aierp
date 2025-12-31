"""
插件加载器
负责从文件或目录加载Python插件
"""
import os
import importlib.util
import importlib
import logging
from typing import List, Optional
from pathlib import Path

from .base import IPlugin, PluginMetadata, PluginStatus

logger = logging.getLogger(__name__)


class PluginLoader:
    """插件加载器"""
    
    def __init__(self, plugin_directory: Optional[str] = None):
        """
        初始化插件加载器
        
        Args:
            plugin_directory: 插件目录，默认为 ${HOME}/plugins
        """
        if plugin_directory is None:
            plugin_directory = os.path.join(os.path.expanduser("~"), "plugins")
        self.plugin_directory = Path(plugin_directory)
        self.plugin_directory.mkdir(parents=True, exist_ok=True)
    
    def load_plugins(self) -> List[IPlugin]:
        """
        加载所有插件
        
        Returns:
            插件列表
        """
        plugins = []
        
        if not self.plugin_directory.exists():
            logger.warning(f"Plugin directory does not exist: {self.plugin_directory}")
            return plugins
        
        # 扫描插件目录
        for item in self.plugin_directory.iterdir():
            try:
                plugin = self.load_plugin(item)
                if plugin:
                    plugins.append(plugin)
            except Exception as e:
                logger.error(f"Failed to load plugin from {item}: {e}", exc_info=True)
        
        logger.info(f"Loaded {len(plugins)} plugins from {self.plugin_directory}")
        return plugins
    
    def load_plugin(self, plugin_path: Path) -> Optional[IPlugin]:
        """
        加载单个插件
        
        Args:
            plugin_path: 插件路径（文件或目录）
        
        Returns:
            插件实例，如果加载失败返回None
        """
        if not plugin_path.exists():
            logger.warning(f"Plugin path does not exist: {plugin_path}")
            return None
        
        try:
            # 单文件插件
            if plugin_path.is_file() and plugin_path.suffix == ".py":
                return self._load_file_plugin(plugin_path)
            
            # 目录形式插件
            elif plugin_path.is_dir():
                return self._load_directory_plugin(plugin_path)
            
            else:
                logger.warning(f"Unsupported plugin format: {plugin_path}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_path}: {e}", exc_info=True)
            return None
    
    def _load_file_plugin(self, file_path: Path) -> Optional[IPlugin]:
        """加载单文件插件"""
        try:
            # 使用importlib加载模块
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for {file_path}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找实现IPlugin接口的类
            plugin_class = self._find_plugin_class(module)
            if plugin_class is None:
                logger.warning(f"No plugin class found in {file_path}")
                return None
            
            # 实例化插件
            plugin = plugin_class()
            return plugin
            
        except Exception as e:
            logger.error(f"Failed to load file plugin {file_path}: {e}", exc_info=True)
            return None
    
    def _load_directory_plugin(self, dir_path: Path) -> Optional[IPlugin]:
        """加载目录形式插件"""
        # 查找main.py或__init__.py
        main_file = dir_path / "main.py"
        if not main_file.exists():
            main_file = dir_path / "__init__.py"
        
        if not main_file.exists():
            logger.warning(f"No main.py or __init__.py found in {dir_path}")
            return None
        
        try:
            # 使用目录名作为模块名
            module_name = dir_path.name
            spec = importlib.util.spec_from_file_location(module_name, main_file)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for {main_file}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            # 添加目录到sys.path以便导入依赖
            import sys
            if str(dir_path.parent) not in sys.path:
                sys.path.insert(0, str(dir_path.parent))
            
            spec.loader.exec_module(module)
            
            # 查找实现IPlugin接口的类
            plugin_class = self._find_plugin_class(module)
            if plugin_class is None:
                logger.warning(f"No plugin class found in {dir_path}")
                return None
            
            # 实例化插件
            plugin = plugin_class()
            return plugin
            
        except Exception as e:
            logger.error(f"Failed to load directory plugin {dir_path}: {e}", exc_info=True)
            return None
    
    def _find_plugin_class(self, module) -> Optional[type]:
        """
        在模块中查找实现IPlugin接口的类
        
        Args:
            module: Python模块
        
        Returns:
            插件类，如果未找到返回None
        """
        from .base import IPlugin
        
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and 
                issubclass(obj, IPlugin) and 
                obj is not IPlugin):
                return obj
        
        return None

