"""
配置管理API接口
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from app.services.config_service import ConfigService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ConfigCreateRequest(BaseModel):
    key: str
    value: Any
    config_type: str = "string"
    category: str = "system"
    description: Optional[str] = None
    is_encrypted: bool = False

class ConfigUpdateRequest(BaseModel):
    value: Any
    config_type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_encrypted: Optional[bool] = None

class LLMConfigRequest(BaseModel):
    # 基础LLM配置
    api_key: str
    base_url: Optional[str] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: Optional[str] = "qwen-max-latest"
    provider: Optional[str] = "qwen"
    timeout: Optional[int] = 15
    max_retries: Optional[int] = 2
    temperature: Optional[float] = 0.2
    unit_price_deepseek: Optional[float] = 0.002
    unit_price_default: Optional[float] = 0.003
    use_real: Optional[bool] = False

    # 前端提交的 Agent 启用配置：{ "sd": { "use_llm": true }, "fi": { "use_llm": true }, ... }
    agent_configs: Optional[Dict[str, Any]] = None

    # Agent特定配置（兼容旧版扁平字段）
    fi_agent_enabled: bool = False
    fi_agent_model: Optional[str] = None
    mm_agent_enabled: bool = False
    mm_agent_model: Optional[str] = None
    pp_agent_enabled: bool = False
    pp_agent_model: Optional[str] = None
    sd_agent_enabled: bool = False
    sd_agent_model: Optional[str] = None
    co_agent_enabled: bool = False
    co_agent_model: Optional[str] = None
    workreport_agent_enabled: bool = False
    workreport_agent_model: Optional[str] = None

def get_config_service() -> ConfigService:
    """获取配置服务实例"""
    return ConfigService()

@router.post("/config")
async def create_or_update_config(
    request: ConfigCreateRequest,
    config_service: ConfigService = Depends(get_config_service),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """创建或更新配置"""
    try:
        config_service.set_config(
            key=request.key,
            value=request.value,
            config_type=request.config_type,
            category=request.category,
            description=request.description,
            is_encrypted=request.is_encrypted
        )
        return {"success": True, "message": "配置保存成功"}
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config/{key}")
async def get_config(
    key: str,
    config_service: ConfigService = Depends(get_config_service)
):
    """获取单个配置"""
    value = config_service.get_config(key)
    if value is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"key": key, "value": value}

@router.get("/config")
async def list_configs(
    category: Optional[str] = None,
    config_service: ConfigService = Depends(get_config_service)
):
    """获取配置列表"""
    if category:
        configs = config_service.get_configs_by_category(category)
    else:
        collection = config_service.db.get_collection("sys_config")
        configs = collection.find({"is_enabled": 1})
    
    result = []
    for config in configs:
        key = config.get("config_key")
        if config.get("is_encrypted"):
            # 加密项也返回解密后的值，供配置管理页面展示
            value = config_service.get_config(key, "")
            if value is None:
                value = ""
        else:
            value = config.get("config_value")
        result.append({
            "key": key,
            "value": value,
            "type": config.get("config_type"),
            "category": config.get("category"),
            "description": config.get("description")
        })
    
    return {"configs": result}

@router.delete("/config/{key}")
async def delete_config(
    key: str,
    config_service: ConfigService = Depends(get_config_service)
):
    """删除配置"""
    try:
        config_service.delete_config(key)
        return {"success": True, "message": "配置删除成功"}
    except Exception as e:
        logger.error(f"删除配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/llm")
async def set_llm_config(
    request: LLMConfigRequest,
    config_service: ConfigService = Depends(get_config_service)
):
    """批量设置LLM配置"""
    try:
        # 设置通用LLM配置
        if request.api_key is not None:
            config_service.set_config(
                "llm.api_key",
                request.api_key.strip() if request.api_key else "",
                category="llm",
                description="LLM API密钥",
                is_encrypted=True
            )
        config_service.set_config(
            "llm.base_url",
            request.base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            category="llm",
            description="LLM API基础URL"
        )
        if request.model:
            config_service.set_config(
                "llm.model",
                request.model,
                category="llm",
                description="默认模型名称"
            )
        config_service.set_config(
            "llm.provider",
            request.provider or "qwen",
            category="llm",
            description="LLM提供商"
        )
        config_service.set_config(
            "llm.timeout",
            request.timeout or 15,
            config_type="number",
            category="llm",
            description="超时时间（秒）"
        )
        config_service.set_config(
            "llm.max_retries",
            request.max_retries or 2,
            config_type="number",
            category="llm",
            description="最大重试次数"
        )
        config_service.set_config(
            "llm.temperature",
            request.temperature or 0.2,
            config_type="number",
            category="llm",
            description="温度参数"
        )
        config_service.set_config(
            "llm.unit_price_deepseek",
            request.unit_price_deepseek or 0.002,
            config_type="number",
            category="llm",
            description="DeepSeek价格（每1000 tokens）"
        )
        config_service.set_config(
            "llm.unit_price_default",
            request.unit_price_default or 0.003,
            config_type="number",
            category="llm",
            description="默认价格（每1000 tokens）"
        )
        config_service.set_config(
            "llm.use_real",
            "true" if request.use_real else "false",
            config_type="boolean",
            category="llm",
            description="是否使用真实LLM调用"
        )
        
        # 设置各Agent配置（优先使用前端提交的 agent_configs）
        if request.agent_configs:
            for agent_name, cfg in request.agent_configs.items():
                if not isinstance(cfg, dict):
                    continue
                enabled = cfg.get("use_llm", False)
                config_service.set_config(
                    f"agent.{agent_name}.use_llm",
                    "true" if enabled else "false",
                    config_type="boolean",
                    category="agent",
                    description=f"{agent_name.upper()} Agent是否启用LLM"
                )
                model = cfg.get("llm_model")
                if model:
                    config_service.set_config(
                        f"agent.{agent_name}.llm_model",
                        model,
                        category="agent",
                        description=f"{agent_name.upper()} Agent自定义模型"
                    )
        else:
            agents = [
                ("fi", request.fi_agent_enabled, request.fi_agent_model),
                ("mm", request.mm_agent_enabled, request.mm_agent_model),
                ("pp", request.pp_agent_enabled, request.pp_agent_model),
                ("sd", request.sd_agent_enabled, request.sd_agent_model),
                ("co", request.co_agent_enabled, request.co_agent_model),
                ("workreport", request.workreport_agent_enabled, request.workreport_agent_model)
            ]
            for agent_name, enabled, model in agents:
                config_service.set_config(
                    f"agent.{agent_name}.use_llm",
                    "true" if enabled else "false",
                    config_type="boolean",
                    category="agent",
                    description=f"{agent_name.upper()} Agent是否启用LLM"
                )
                if model:
                    config_service.set_config(
                        f"agent.{agent_name}.llm_model",
                        model,
                        category="agent",
                        description=f"{agent_name.upper()} Agent使用的模型"
                    )
                else:
                    try:
                        config_service.delete_config(f"agent.{agent_name}.llm_model")
                    except Exception:
                        pass

        return {"success": True, "message": "LLM配置保存成功"}
    except Exception as e:
        logger.error(f"保存LLM配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config/llm/status/{agent_name}")
async def get_llm_status(
    agent_name: str,
    config_service: ConfigService = Depends(get_config_service)
):
    """检查Agent的LLM配置状态"""
    is_enabled = config_service.is_llm_enabled(agent_name)
    return {
        "agent_name": agent_name,
        "llm_enabled": is_enabled,
        "has_api_key": bool(config_service.get_config("llm.api_key", "")),
        "has_base_url": bool(config_service.get_config("llm.base_url", ""))
    }

@router.post("/config/llm/test")
async def test_llm_connection(
    request: Dict[str, Any],
    config_service: ConfigService = Depends(get_config_service)
):
    """测试LLM连接"""
    try:
        api_key = request.get("api_key", "")
        base_url = request.get("base_url", "")
        model = request.get("model", "qwen-max-latest")
        
        if not api_key or not base_url:
            return {
                "success": False,
                "message": "API密钥和Base URL不能为空"
            }
        
        # 尝试调用LLM API
        import requests
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "测试"}
                ],
                "max_tokens": 10
            },
            timeout=10
        )
        
        if resp.status_code == 200:
            return {
                "success": True,
                "message": "连接成功，LLM配置有效"
            }
        else:
            return {
                "success": False,
                "message": f"连接失败：{resp.status_code} - {resp.text[:100]}"
            }
    except Exception as e:
        logger.error(f"测试LLM连接失败: {e}")
        return {
            "success": False,
            "message": f"连接失败：{str(e)}"
        }
