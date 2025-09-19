"""
Flink实时数据流处理器
负责采集和处理流程日志，实现实时监控和告警
"""

import json
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProcessType(Enum):
    ORDER_SYNC = "order_sync"
    INVENTORY_SYNC = "inventory_sync"
    FINANCE_RECONCILE = "finance_reconcile"
    SUPPLIER_SYNC = "supplier_sync"
    DATA_VALIDATION = "data_validation"


@dataclass
class ProcessLog:
    """流程日志"""
    log_id: str
    process_type: ProcessType
    timestamp: float
    level: LogLevel
    message: str
    source_system: str
    target_system: str
    duration_ms: Optional[int] = None
    records_processed: Optional[int] = None
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProcessAlert:
    """流程告警"""
    alert_id: str
    process_type: ProcessType
    alert_level: LogLevel
    message: str
    timestamp: float
    source_log_id: str
    resolution: Optional[str] = None
    auto_fix_applied: bool = False


class StreamProcessor:
    """流处理器"""
    
    def __init__(self):
        self.processors: List[Callable[[ProcessLog], Optional[ProcessAlert]]] = []
        self.alert_handlers: List[Callable[[ProcessAlert], None]] = []
        self.running = False
        self.log_queue: List[ProcessLog] = []
        self._lock = threading.Lock()
        self._processing_thread = None
    
    def add_processor(self, processor: Callable[[ProcessLog], Optional[ProcessAlert]]):
        """添加日志处理器"""
        self.processors.append(processor)
    
    def add_alert_handler(self, handler: Callable[[ProcessAlert], None]):
        """添加告警处理器"""
        self.alert_handlers.append(handler)
    
    def start(self):
        """启动流处理器"""
        if self.running:
            return
        
        self.running = True
        self._processing_thread = threading.Thread(target=self._process_loop)
        self._processing_thread.daemon = True
        self._processing_thread.start()
        logger.info("流处理器已启动")
    
    def stop(self):
        """停止流处理器"""
        self.running = False
        if self._processing_thread:
            self._processing_thread.join(timeout=5)
        logger.info("流处理器已停止")
    
    def submit_log(self, log: ProcessLog):
        """提交日志"""
        with self._lock:
            self.log_queue.append(log)
    
    def _process_loop(self):
        """处理循环"""
        while self.running:
            try:
                with self._lock:
                    if not self.log_queue:
                        time.sleep(0.1)
                        continue
                    
                    log = self.log_queue.pop(0)
                
                # 处理日志
                for processor in self.processors:
                    try:
                        alert = processor(log)
                        if alert:
                            self._handle_alert(alert)
                    except Exception as e:
                        logger.error(f"处理器执行失败: {e}")
                
            except Exception as e:
                logger.error(f"流处理循环错误: {e}")
                time.sleep(1)


class ProcessMonitor:
    """流程监控器"""
    
    def __init__(self):
        self.processor = StreamProcessor()
        self.alert_rules: List[Dict[str, Any]] = []
        self.performance_metrics: Dict[str, List[float]] = {}
        self._setup_default_processors()
        self._setup_default_rules()
    
    def _setup_default_processors(self):
        """设置默认处理器"""
        self.processor.add_processor(self._duration_processor)
        self.processor.add_processor(self._error_processor)
        self.processor.add_processor(self._performance_processor)
        self.processor.add_alert_handler(self._log_alert_handler)
    
    def _setup_default_rules(self):
        """设置默认规则"""
        self.alert_rules = [
            {
                "name": "duration_threshold",
                "condition": lambda log: log.duration_ms and log.duration_ms > 30000,  # 30秒
                "level": LogLevel.WARNING,
                "message": "流程执行时间过长",
                "resolution": "检查网络连接和数据库性能"
            },
            {
                "name": "error_rate",
                "condition": lambda log: log.level in [LogLevel.ERROR, LogLevel.CRITICAL],
                "level": LogLevel.ERROR,
                "message": "流程执行出现错误",
                "resolution": "检查系统配置和依赖服务"
            },
            {
                "name": "low_throughput",
                "condition": lambda log: (log.records_processed and log.duration_ms 
                                        and log.records_processed / (log.duration_ms / 1000) < 10),
                "level": LogLevel.WARNING,
                "message": "数据处理吞吐量过低",
                "resolution": "优化查询语句和索引"
            }
        ]
    
    def _duration_processor(self, log: ProcessLog) -> Optional[ProcessAlert]:
        """处理执行时间"""
        if log.duration_ms and log.duration_ms > 30000:  # 30秒阈值
            return ProcessAlert(
                alert_id=str(uuid.uuid4()),
                process_type=log.process_type,
                alert_level=LogLevel.WARNING,
                message=f"流程执行时间过长: {log.duration_ms}ms",
                timestamp=time.time(),
                source_log_id=log.log_id,
                resolution="检查网络连接和数据库性能"
            )
        return None
    
    def _error_processor(self, log: ProcessLog) -> Optional[ProcessAlert]:
        """处理错误"""
        if log.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            return ProcessAlert(
                alert_id=str(uuid.uuid4()),
                process_type=log.process_type,
                alert_level=log.level,
                message=f"流程执行错误: {log.message}",
                timestamp=time.time(),
                source_log_id=log.log_id,
                resolution="检查系统配置和依赖服务"
            )
        return None
    
    def _performance_processor(self, log: ProcessLog) -> Optional[ProcessAlert]:
        """处理性能指标"""
        if log.records_processed and log.duration_ms:
            throughput = log.records_processed / (log.duration_ms / 1000)
            
            # 记录性能指标
            process_key = f"{log.process_type.value}_{log.source_system}"
            if process_key not in self.performance_metrics:
                self.performance_metrics[process_key] = []
            
            self.performance_metrics[process_key].append(throughput)
            
            # 保持最近100个记录
            if len(self.performance_metrics[process_key]) > 100:
                self.performance_metrics[process_key] = self.performance_metrics[process_key][-100:]
            
            # 检查吞吐量是否过低
            if throughput < 10:  # 每秒处理记录数少于10
                return ProcessAlert(
                    alert_id=str(uuid.uuid4()),
                    process_type=log.process_type,
                    alert_level=LogLevel.WARNING,
                    message=f"数据处理吞吐量过低: {throughput:.2f} records/s",
                    timestamp=time.time(),
                    source_log_id=log.log_id,
                    resolution="优化查询语句和索引"
                )
        
        return None
    
    def _log_alert_handler(self, alert: ProcessAlert):
        """告警处理器"""
        logger.warning(f"流程告警: {alert.message} - {alert.resolution}")
        # 这里可以添加更多告警处理逻辑，如发送邮件、短信等
    
    def start_monitoring(self):
        """开始监控"""
        self.processor.start()
        logger.info("流程监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.processor.stop()
        logger.info("流程监控已停止")
    
    def log_process_event(self, process_type: ProcessType, level: LogLevel,
                         message: str, source_system: str, target_system: str,
                         duration_ms: Optional[int] = None,
                         records_processed: Optional[int] = None,
                         error_code: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None):
        """记录流程事件"""
        log = ProcessLog(
            log_id=str(uuid.uuid4()),
            process_type=process_type,
            timestamp=time.time(),
            level=level,
            message=message,
            source_system=source_system,
            target_system=target_system,
            duration_ms=duration_ms,
            records_processed=records_processed,
            error_code=error_code,
            metadata=metadata
        )
        
        self.processor.submit_log(log)
    
    def get_performance_metrics(self, process_type: Optional[ProcessType] = None) -> Dict[str, List[float]]:
        """获取性能指标"""
        if process_type:
            return {k: v for k, v in self.performance_metrics.items() 
                   if k.startswith(process_type.value)}
        return self.performance_metrics
    
    def get_recent_alerts(self, limit: int = 50) -> List[ProcessAlert]:
        """获取最近的告警"""
        # 这里应该从数据库查询，现在返回空列表
        return []


class FlinkStreamManager:
    """Flink流管理器"""
    
    def __init__(self):
        self.monitor = ProcessMonitor()
        self.running = False
    
    def start_stream_processing(self):
        """启动流处理"""
        if self.running:
            return
        
        self.running = True
        self.monitor.start_monitoring()
        logger.info("Flink流处理已启动")
    
    def stop_stream_processing(self):
        """停止流处理"""
        if not self.running:
            return
        
        self.running = False
        self.monitor.stop_monitoring()
        logger.info("Flink流处理已停止")
    
    def simulate_process_logs(self):
        """模拟流程日志（用于测试）"""
        import random
        
        process_types = list(ProcessType)
        levels = [LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR]
        systems = ["SAP", "UFIDA", "Snowflake", "MongoDB"]
        
        for _ in range(10):
            process_type = random.choice(process_types)
            level = random.choice(levels)
            source = random.choice(systems)
            target = random.choice([s for s in systems if s != source])
            
            duration = random.randint(1000, 60000) if random.random() > 0.3 else None
            records = random.randint(100, 10000) if random.random() > 0.2 else None
            
            self.monitor.log_process_event(
                process_type=process_type,
                level=level,
                message=f"模拟{process_type.value}流程事件",
                source_system=source,
                target_system=target,
                duration_ms=duration,
                records_processed=records
            )
            
            time.sleep(0.1)  # 模拟日志间隔
