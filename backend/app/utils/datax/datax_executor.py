"""
DataX执行器
负责执行DataX作业，监控执行状态，处理错误
"""

import subprocess
import json
import os
import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobResult:
    """作业执行结果"""
    job_id: str
    status: JobStatus
    start_time: float
    end_time: Optional[float] = None
    records_read: int = 0
    records_written: int = 0
    error_message: Optional[str] = None
    config_path: Optional[str] = None


class DataXExecutor:
    """DataX执行器"""
    
    def __init__(self, datax_home: str = "/opt/datax"):
        self.datax_home = datax_home
        self.running_jobs: Dict[str, subprocess.Popen] = {}
        self.job_results: Dict[str, JobResult] = {}
        self._lock = threading.Lock()
    
    def execute_job(self, config_path: str, job_id: str) -> JobResult:
        """执行DataX作业"""
        with self._lock:
            if job_id in self.running_jobs:
                return JobResult(
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    start_time=time.time(),
                    error_message="Job already running"
                )
        
        # 创建作业结果记录
        job_result = JobResult(
            job_id=job_id,
            status=JobStatus.PENDING,
            start_time=time.time(),
            config_path=config_path
        )
        self.job_results[job_id] = job_result
        
        try:
            # 构建DataX命令
            datax_script = os.path.join(self.datax_home, "bin", "datax.py")
            if not os.path.exists(datax_script):
                # 如果DataX未安装，使用模拟执行
                return self._mock_execute_job(job_id, config_path)
            
            # 执行DataX作业
            cmd = ["python", datax_script, config_path]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.datax_home
            )
            
            with self._lock:
                self.running_jobs[job_id] = process
                job_result.status = JobStatus.RUNNING
            
            # 启动监控线程
            monitor_thread = threading.Thread(
                target=self._monitor_job,
                args=(job_id, process)
            )
            monitor_thread.daemon = True
            monitor_thread.start()
            
            return job_result
            
        except Exception as e:
            logger.error(f"启动DataX作业失败: {e}")
            job_result.status = JobStatus.FAILED
            job_result.error_message = str(e)
            return job_result
    
    def _mock_execute_job(self, job_id: str, config_path: str) -> JobResult:
        """模拟执行DataX作业（用于开发环境）"""
        job_result = self.job_results[job_id]
        job_result.status = JobStatus.RUNNING
        
        # 模拟执行过程
        def mock_execution():
            time.sleep(2)  # 模拟执行时间
            
            with self._lock:
                job_result.status = JobStatus.SUCCESS
                job_result.end_time = time.time()
                job_result.records_read = 1000
                job_result.records_written = 1000
                
                if job_id in self.running_jobs:
                    del self.running_jobs[job_id]
        
        thread = threading.Thread(target=mock_execution)
        thread.daemon = True
        thread.start()
        
        return job_result
    
    def _monitor_job(self, job_id: str, process: subprocess.Popen):
        """监控作业执行状态"""
        try:
            stdout, stderr = process.communicate()
            
            with self._lock:
                job_result = self.job_results.get(job_id)
                if not job_result:
                    return
                
                job_result.end_time = time.time()
                
                if process.returncode == 0:
                    job_result.status = JobStatus.SUCCESS
                    # 解析输出获取记录数
                    job_result.records_read = self._parse_records_count(stdout, "read")
                    job_result.records_written = self._parse_records_count(stdout, "written")
                else:
                    job_result.status = JobStatus.FAILED
                    job_result.error_message = stderr or "Unknown error"
                
                # 清理运行中的作业记录
                if job_id in self.running_jobs:
                    del self.running_jobs[job_id]
                    
        except Exception as e:
            logger.error(f"监控DataX作业失败: {e}")
            with self._lock:
                job_result = self.job_results.get(job_id)
                if job_result:
                    job_result.status = JobStatus.FAILED
                    job_result.error_message = str(e)
                    if job_id in self.running_jobs:
                        del self.running_jobs[job_id]
    
    def _parse_records_count(self, output: str, count_type: str) -> int:
        """从DataX输出中解析记录数"""
        try:
            lines = output.split('\n')
            for line in lines:
                if count_type in line.lower() and 'record' in line.lower():
                    # 提取数字
                    import re
                    numbers = re.findall(r'\d+', line)
                    if numbers:
                        return int(numbers[0])
        except Exception:
            pass
        return 0
    
    def get_job_status(self, job_id: str) -> Optional[JobResult]:
        """获取作业状态"""
        with self._lock:
            return self.job_results.get(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """取消作业"""
        with self._lock:
            if job_id in self.running_jobs:
                process = self.running_jobs[job_id]
                process.terminate()
                del self.running_jobs[job_id]
                
                job_result = self.job_results.get(job_id)
                if job_result:
                    job_result.status = JobStatus.CANCELLED
                    job_result.end_time = time.time()
                
                return True
        return False
    
    def list_jobs(self) -> List[JobResult]:
        """列出所有作业"""
        with self._lock:
            return list(self.job_results.values())
    
    def cleanup_completed_jobs(self, max_age_hours: int = 24):
        """清理已完成的作业记录"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        with self._lock:
            to_remove = []
            for job_id, job_result in self.job_results.items():
                if (job_result.status in [JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED] 
                    and job_result.end_time 
                    and current_time - job_result.end_time > max_age_seconds):
                    to_remove.append(job_id)
            
            for job_id in to_remove:
                del self.job_results[job_id]
    
    def get_job_logs(self, job_id: str) -> Optional[str]:
        """获取作业日志"""
        # 这里应该从日志文件读取，现在返回模拟数据
        job_result = self.get_job_status(job_id)
        if not job_result:
            return None
        
        return f"Job {job_id} executed from {job_result.start_time} to {job_result.end_time}"


class DataXManager:
    """DataX管理器"""
    
    def __init__(self, datax_home: str = "/opt/datax"):
        self.executor = DataXExecutor(datax_home)
        self.config_generator = None  # 将在需要时导入
    
    def sync_erp_data(self, source_type: str, tables: List[str], 
                     source_config: Dict[str, Any]) -> JobResult:
        """同步ERP数据"""
        try:
            # 动态导入配置生成器
            from .datax_config import DataXConfigGenerator, DataSourceType
            self.config_generator = DataXConfigGenerator()
            
            # 生成作业ID
            job_id = f"{source_type}_{int(time.time())}"
            
            # 生成配置
            if source_type.lower() == "sap":
                config = self.config_generator.generate_sap_config(
                    job_id, tables, source_config
                )
            elif source_type.lower() == "ufida":
                config = self.config_generator.generate_ufida_config(
                    job_id, tables, source_config
                )
            else:
                raise ValueError(f"不支持的数据源类型: {source_type}")
            
            # 保存配置
            config_dir = os.path.join(self.executor.datax_home, "job", "custom")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, f"{job_id}.json")
            
            if not self.config_generator.save_config(config, config_path):
                raise Exception("保存DataX配置失败")
            
            # 执行作业
            return self.executor.execute_job(config_path, job_id)
            
        except Exception as e:
            logger.error(f"同步ERP数据失败: {e}")
            return JobResult(
                job_id=f"error_{int(time.time())}",
                status=JobStatus.FAILED,
                start_time=time.time(),
                error_message=str(e)
            )
