from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from ...utils.snowflake_client import execute_query, execute_many
from ...utils.parsers.unstructured_parser import detect_and_parse
from ...utils.llm.data_extract import extract_from_unstructured
from ...utils.llm.field_mapping import FieldMappingGenerator
from ...utils.datax.datax_executor import DataXManager
from ...utils.flink.stream_processor import FlinkStreamManager, ProcessType, LogLevel
import os
import logging
import time
import asyncio

logger = logging.getLogger(__name__)

# 说明：数据集成模块接口，集成DataX、Flink和LLM功能

router = APIRouter()

# 全局管理器实例
datax_manager = DataXManager()
flink_manager = FlinkStreamManager()

class SyncRequest(BaseModel):
    source: str  # 数据源标识，如 SAP/用友
    tables: list[str]  # 需要同步的表
    source_config: Optional[Dict[str, Any]] = None  # 源系统配置
    use_datax: bool = True  # 是否使用DataX
    real_time: bool = False  # 是否实时同步


@router.post("/sync")
async def data_sync(payload: SyncRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """数据同步接口，支持DataX和实时流处理"""
    try:
        # 记录同步开始
        sync_id = f"sync_{int(time.time())}"
        logger.info(f"开始数据同步: {sync_id}, 源: {payload.source}, 表: {payload.tables}")
        
        # 检查Snowflake配置
        required = [
            "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
            "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA",
        ]
        snowflake_configured = all(os.getenv(k) for k in required)
        
        if not snowflake_configured:
            logger.warning("Snowflake未配置，使用模拟同步")
            return await _mock_data_sync(payload, sync_id)
        
        # 使用DataX进行同步
        if payload.use_datax:
            return await _datax_sync(payload, sync_id, background_tasks)
        else:
            return await _direct_sync(payload, sync_id)
            
    except Exception as e:
        logger.error(f"数据同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据同步失败: {str(e)}")


async def _datax_sync(payload: SyncRequest, sync_id: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """使用DataX进行数据同步"""
    try:
        # 准备源系统配置
        source_config = payload.source_config or _get_default_source_config(payload.source)
        
        # 启动Flink流处理（如果启用实时同步）
        if payload.real_time:
            flink_manager.start_stream_processing()
            background_tasks.add_task(_simulate_realtime_logs, payload.source, payload.tables)
        
        # 执行DataX同步
        job_result = datax_manager.sync_erp_data(
            source_type=payload.source,
            tables=payload.tables,
            source_config=source_config
        )
        
        # 记录同步日志
        _log_sync_event(payload.source, payload.tables, job_result)
        
        return {
            "sync_id": sync_id,
            "status": job_result.status.value,
            "job_id": job_result.job_id,
            "tables": payload.tables,
            "records_read": job_result.records_read,
            "records_written": job_result.records_written,
            "duration_ms": (job_result.end_time - job_result.start_time) * 1000 if job_result.end_time else None,
            "error_message": job_result.error_message,
            "real_time_enabled": payload.real_time
        }
        
    except Exception as e:
        logger.error(f"DataX同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"DataX同步失败: {str(e)}")


async def _direct_sync(payload: SyncRequest, sync_id: str) -> Dict[str, Any]:
    """直接数据库同步（不使用DataX）"""
    try:
        # 创建同步日志表
        execute_query("create table if not exists SYNC_LOG(source string, table_name string, sync_time timestamp)")
        
        # 记录同步开始
        rows = [(payload.source, t, time.time()) for t in payload.tables]
        execute_many("insert into SYNC_LOG(source, table_name, sync_time) values(%s, %s, %s)", rows)
        
        # 获取最近同步记录
        recent_data = execute_query("select source, table_name, sync_time from SYNC_LOG order by sync_time desc limit 5")
        
        return {
            "sync_id": sync_id,
            "status": "success",
            "synced": len(rows),
            "recent": recent_data,
            "method": "direct_sync"
        }
        
    except Exception as e:
        logger.error(f"直接同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"直接同步失败: {str(e)}")


async def _mock_data_sync(payload: SyncRequest, sync_id: str) -> Dict[str, Any]:
    """模拟数据同步（用于开发环境）"""
    # 模拟同步延迟
    await asyncio.sleep(1)
    
    return {
        "sync_id": sync_id,
        "status": "success",
        "synced": len(payload.tables),
        "recent": [{"source": payload.source, "table_name": table} for table in payload.tables],
        "note": "snowflake not configured, dry-run",
        "method": "mock_sync"
    }


def _get_default_source_config(source: str) -> Dict[str, Any]:
    """获取默认源系统配置"""
    if source.lower() == "sap":
        return {
            "username": os.getenv("SAP_USERNAME", "sap_user"),
            "password": os.getenv("SAP_PASSWORD", "sap_pass"),
            "host": os.getenv("SAP_HOST", "sap.example.com"),
            "port": int(os.getenv("SAP_PORT", "8000")),
            "client": os.getenv("SAP_CLIENT", "000"),
            "system_number": os.getenv("SAP_SYSTEM", "00"),
            "snowflake_username": os.getenv("SNOWFLAKE_USER"),
            "snowflake_password": os.getenv("SNOWFLAKE_PASSWORD"),
            "snowflake_url": f"jdbc:snowflake://{os.getenv('SNOWFLAKE_ACCOUNT')}.snowflakecomputing.com/",
            "snowflake_schema": os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
        }
    elif source.lower() == "ufida":
        return {
            "username": os.getenv("UFIDA_USERNAME", "ufida_user"),
            "password": os.getenv("UFIDA_PASSWORD", "ufida_pass"),
            "jdbc_url": os.getenv("UFIDA_JDBC_URL", "jdbc:mysql://ufida.example.com:3306/ufida"),
            "snowflake_username": os.getenv("SNOWFLAKE_USER"),
            "snowflake_password": os.getenv("SNOWFLAKE_PASSWORD"),
            "snowflake_url": f"jdbc:snowflake://{os.getenv('SNOWFLAKE_ACCOUNT')}.snowflakecomputing.com/",
            "snowflake_schema": os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
        }
    else:
        return {}


def _log_sync_event(source: str, tables: List[str], job_result) -> None:
    """记录同步事件到Flink流"""
    try:
        process_type = ProcessType.DATA_VALIDATION if "validation" in str(tables) else ProcessType.ORDER_SYNC
        
        flink_manager.monitor.log_process_event(
            process_type=process_type,
            level=LogLevel.INFO if job_result.status.value == "success" else LogLevel.ERROR,
            message=f"数据同步完成: {source} -> {tables}",
            source_system=source,
            target_system="Snowflake",
            duration_ms=int((job_result.end_time - job_result.start_time) * 1000) if job_result.end_time else None,
            records_processed=job_result.records_written,
            error_code=job_result.error_message
        )
    except Exception as e:
        logger.error(f"记录同步事件失败: {e}")


async def _simulate_realtime_logs(source: str, tables: List[str]) -> None:
    """模拟实时日志（后台任务）"""
    try:
        for _ in range(5):  # 模拟5个日志事件
            flink_manager.monitor.log_process_event(
                process_type=ProcessType.ORDER_SYNC,
                level=LogLevel.INFO,
                message=f"实时同步处理: {source}",
                source_system=source,
                target_system="Snowflake",
                duration_ms=1000 + (hash(str(tables)) % 5000),
                records_processed=100 + (hash(str(tables)) % 900)
            )
            await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"模拟实时日志失败: {e}")


@router.post("/field-mapping")
async def generate_field_mapping(
    source_fields: List[str],
    target_fields: List[str],
    source_system: str = "",
    target_system: str = ""
) -> Dict[str, Any]:
    """生成字段映射规则"""
    try:
        generator = FieldMappingGenerator()
        result = generator.generate_field_mapping(
            source_fields=source_fields,
            target_fields=target_fields,
            source_system=source_system,
            target_system=target_system
        )
        
        # 验证映射结果
        validation = generator.validate_mapping(result)
        result["validation"] = validation
        
        return result
        
    except Exception as e:
        logger.error(f"生成字段映射失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成字段映射失败: {str(e)}")


@router.get("/sync-status/{job_id}")
async def get_sync_status(job_id: str) -> Dict[str, Any]:
    """获取同步作业状态"""
    try:
        job_result = datax_manager.executor.get_job_status(job_id)
        if not job_result:
            raise HTTPException(status_code=404, detail="作业不存在")
        
        return {
            "job_id": job_id,
            "status": job_result.status.value,
            "start_time": job_result.start_time,
            "end_time": job_result.end_time,
            "duration_ms": (job_result.end_time - job_result.start_time) * 1000 if job_result.end_time else None,
            "records_read": job_result.records_read,
            "records_written": job_result.records_written,
            "error_message": job_result.error_message
        }
        
    except Exception as e:
        logger.error(f"获取同步状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取同步状态失败: {str(e)}")


@router.get("/stream-metrics")
async def get_stream_metrics() -> Dict[str, Any]:
    """获取流处理指标"""
    try:
        metrics = flink_manager.monitor.get_performance_metrics()
        alerts = flink_manager.monitor.get_recent_alerts(limit=10)
        
        return {
            "performance_metrics": metrics,
            "recent_alerts": [
                {
                    "alert_id": alert.alert_id,
                    "process_type": alert.process_type.value,
                    "level": alert.alert_level.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp,
                    "resolution": alert.resolution
                } for alert in alerts
            ],
            "stream_running": flink_manager.running
        }
        
    except Exception as e:
        logger.error(f"获取流处理指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取流处理指标失败: {str(e)}")


@router.post("/parse-unstructured")
async def parse_unstructured(file: UploadFile = File(...)) -> Dict[str, Any]:
    filename = file.filename
    content = await file.read()
    ftype, text = detect_and_parse(filename, content)
    llm = extract_from_unstructured(text.encode("utf-8"), ftype)
    return {"filename": filename, "type": ftype, "preview": text[:500], "llm": llm}


