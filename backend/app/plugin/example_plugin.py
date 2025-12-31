"""
示例Python插件
演示如何实现IPlugin接口并开发业务功能
"""
import logging
from typing import Dict, Any

from .base import IPlugin, PluginMetadata, PluginStatus, PluginContext

logger = logging.getLogger(__name__)


class ExampleBusinessPlugin(IPlugin):
    """示例业务插件"""
    
    def __init__(self):
        """初始化插件"""
        self.metadata: PluginMetadata = None
        self.context: PluginContext = None
        self.status = PluginStatus.INSTALLED
        self.business_service = None
    
    def get_metadata(self) -> PluginMetadata:
        """获取插件元信息"""
        if self.metadata is None:
            from .base import PluginMetadata
            self.metadata = PluginMetadata(
                plugin_id="example-python-plugin",
                plugin_name="示例Python插件",
                version="1.0.0",
                description="这是一个示例Python插件，演示如何开发和使用插件系统",
                author="AI ERP Platform",
                vendor="SinoCST",
                plugin_class="ExampleBusinessPlugin"
            )
        return self.metadata
    
    def initialize(self, context: PluginContext) -> None:
        """初始化插件"""
        logger.info("Initializing example Python plugin...")
        self.context = context
        self.metadata = self.get_metadata()
        
        # 初始化业务服务
        self.business_service = ExampleBusinessService()
        
        self.status = PluginStatus.INITIALIZED
        logger.info("Example Python plugin initialized successfully")
    
    def start(self) -> None:
        """启动插件"""
        logger.info("Starting example Python plugin...")
        
        if self.status not in [PluginStatus.INITIALIZED, PluginStatus.STOPPED]:
            raise RuntimeError("Plugin must be initialized before starting")
        
        # 启动业务服务
        if self.business_service:
            self.business_service.start()
        
        self.status = PluginStatus.STARTED
        logger.info("Example Python plugin started successfully")
    
    def stop(self) -> None:
        """停止插件"""
        logger.info("Stopping example Python plugin...")
        
        # 停止业务服务
        if self.business_service:
            self.business_service.stop()
        
        self.status = PluginStatus.STOPPED
        logger.info("Example Python plugin stopped successfully")
    
    def destroy(self) -> None:
        """销毁插件"""
        logger.info("Destroying example Python plugin...")
        
        # 清理资源
        self.business_service = None
        self.context = None
        
        logger.info("Example Python plugin destroyed")
    
    def get_services(self) -> Dict[str, Any]:
        """获取插件提供的服务"""
        services = {}
        if self.business_service:
            services["exampleBusinessService"] = self.business_service
        return services
    
    def get_status(self) -> PluginStatus:
        """获取插件当前状态"""
        return self.status


class ExampleBusinessService:
    """示例业务服务"""
    
    def __init__(self):
        """初始化服务"""
        self.running = False
    
    def start(self) -> None:
        """启动服务"""
        if self.running:
            logger.warning("Example business service is already running")
            return
        self.running = True
        logger.info("Example business service started")
    
    def stop(self) -> None:
        """停止服务"""
        if not self.running:
            logger.warning("Example business service is not running")
            return
        self.running = False
        logger.info("Example business service stopped")
    
    def process_business(self, input_data: str) -> str:
        """
        执行业务操作
        
        Args:
            input_data: 输入参数
        
        Returns:
            处理结果
        """
        if not self.running:
            raise RuntimeError("Service is not running")
        logger.info(f"Processing business: {input_data}")
        return f"Processed: {input_data}"
    
    def is_running(self) -> bool:
        """检查服务状态"""
        return self.running

