"""
配置服务
提供配置的增删改查功能，支持加密存储敏感信息
"""
import logging
import json
import os
from typing import Optional, Dict, List, Any
from app.db.sqlite_db import get_sqlite_db

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("cryptography库未安装，加密功能将不可用")


class ConfigService:
    """配置服务类"""
    
    def __init__(self):
        self.db = get_sqlite_db()
        self._init_encryption_key()
    
    def _init_encryption_key(self):
        """初始化加密密钥"""
        if not CRYPTOGRAPHY_AVAILABLE:
            self.cipher = None
            return
        
        # 从环境变量获取密钥
        key = os.getenv("CONFIG_ENCRYPTION_KEY")
        if not key:
            # 如果没有配置，生成一个固定的密钥（仅用于开发环境）
            # 生产环境应该从密钥管理服务获取
            logger.warning("未配置CONFIG_ENCRYPTION_KEY，使用默认密钥（仅开发环境）")
            # 生成一个固定的密钥用于开发（32字节base64编码）
            key = "dev_key_32_bytes_1234567890123456"  # 仅用于开发
        
        try:
            # 确保密钥是32字节的base64编码
            if len(key) < 32:
                key = key.ljust(32, '0')
            key = key[:32]
            # 转换为Fernet需要的格式
            import base64
            key_bytes = base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b'0'))
            self.cipher = Fernet(key_bytes)
        except Exception as e:
            logger.error(f"初始化加密密钥失败: {e}")
            self.cipher = None
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        collection = self.db.get_collection("sys_config")
        config = collection.find_one({"config_key": key, "is_enabled": 1})
        
        if not config:
            return default
        
        value = config.get("config_value")
        if not value:
            return default
        
        # 解密加密的配置
        if config.get("is_encrypted") and self.cipher:
            try:
                value = self.cipher.decrypt(value.encode()).decode()
            except Exception as e:
                logger.error(f"解密配置失败 {key}: {e}")
                return default
        
        # 根据类型转换
        config_type = config.get("config_type", "string")
        if config_type == "number":
            try:
                return float(value) if '.' in str(value) else int(value)
            except ValueError:
                return default
        elif config_type == "boolean":
            return str(value).lower() in ("true", "1", "yes")
        elif config_type == "json":
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default
        return value
    
    def set_config(self, key: str, value: Any, config_type: str = "string", 
                   category: str = "system", description: str = None,
                   is_encrypted: bool = False, created_by: str = None) -> bool:
        """设置配置值"""
        collection = self.db.get_collection("sys_config")
        
        # 处理值
        if config_type == "json":
            value_str = json.dumps(value, ensure_ascii=False)
        else:
            value_str = str(value)
        
        # 加密敏感信息
        if is_encrypted and self.cipher:
            try:
                value_str = self.cipher.encrypt(value_str.encode()).decode()
            except Exception as e:
                logger.error(f"加密配置失败 {key}: {e}")
                return False
        
        # 检查是否存在
        existing = collection.find_one({"config_key": key})
        
        if existing:
            # 更新
            update_data = {
                "config_value": value_str,
                "config_type": config_type,
                "category": category,
                "is_encrypted": 1 if is_encrypted else 0,
                "updated_at": "datetime('now')"
            }
            if description:
                update_data["description"] = description
            if created_by:
                update_data["updated_by"] = created_by
            
            collection.update_one({"config_key": key}, update_data)
        else:
            # 插入
            insert_data = {
                "config_key": key,
                "config_value": value_str,
                "config_type": config_type,
                "category": category,
                "is_encrypted": 1 if is_encrypted else 0,
                "is_enabled": 1,
                "created_by": created_by,
                "updated_by": created_by
            }
            if description:
                insert_data["description"] = description
            
            collection.insert_one(insert_data)
        
        return True
    
    def delete_config(self, key: str) -> bool:
        """删除配置"""
        collection = self.db.get_collection("sys_config")
        collection.delete_one({"config_key": key})
        return True
    
    def get_configs_by_category(self, category: str) -> List[Dict]:
        """按分类获取配置"""
        collection = self.db.get_collection("sys_config")
        configs = collection.find({"category": category, "is_enabled": 1})
        return list(configs)
    
    def is_llm_enabled(self, agent_name: str) -> bool:
        """检查Agent是否启用LLM"""
        import os
        
        # 优先读取数据库配置
        use_llm = self.get_config(f"agent.{agent_name}.use_llm")
        if use_llm is not None:
            api_key = self.get_config("llm.api_key", "")
            base_url = self.get_config("llm.base_url", "")
            # 只有配置了use_llm=true且配置了api_key和base_url才启用
            return use_llm and bool(api_key) and bool(base_url)
        
        # Fallback到环境变量（向后兼容）
        env_key = f"USE_LLM_{agent_name.upper()}_AGENT"
        use_llm = os.getenv(env_key, "false").lower() == "true"
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "")
        return use_llm and bool(api_key) and bool(base_url)
    
    def get_llm_config(self, agent_name: str) -> Dict[str, Any]:
        """获取Agent的LLM配置"""
        import os
        
        # 优先从数据库读取，如果不存在则从环境变量读取，最后使用默认值
        def get_config_with_fallback(key: str, default: Any = None, env_keys: List[str] = None):
            # 先尝试从数据库读取
            value = self.get_config(key)
            if value is not None and value != "":
                return value
            
            # 再尝试从环境变量读取
            if env_keys:
                for env_key in env_keys:
                    env_value = os.getenv(env_key)
                    if env_value:
                        return env_value
            
            # 最后使用默认值
            return default
        
        # 获取模型名称（Agent特定 > 默认模型）
        agent_model = self.get_config(f"agent.{agent_name}.llm_model")
        default_model = get_config_with_fallback(
            "llm.model",
            "qwen-max-latest",
            ["LLM_MODEL", f"{agent_name.upper()}_AGENT_LLM_MODEL"]
        )
        model = agent_model or default_model
        
        return {
            "api_key": get_config_with_fallback(
                "llm.api_key",
                "",
                ["OPENAI_API_KEY", "LLM_API_KEY"]
            ),
            "base_url": get_config_with_fallback(
                "llm.base_url",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
                ["OPENAI_BASE_URL", "LLM_API_BASE"]
            ),
            "model": model,
            "provider": get_config_with_fallback(
                "llm.provider",
                "qwen",
                []
            ),
            "timeout": get_config_with_fallback(
                "llm.timeout",
                15,
                []
            ),
            "max_retries": get_config_with_fallback(
                "llm.max_retries",
                2,
                []
            ),
            "temperature": get_config_with_fallback(
                "llm.temperature",
                0.2,
                []
            ),
            "unit_price_deepseek": get_config_with_fallback(
                "llm.unit_price_deepseek",
                0.002,
                []
            ),
            "unit_price_default": get_config_with_fallback(
                "llm.unit_price_default",
                0.003,
                []
            ),
            "use_real": get_config_with_fallback(
                "llm.use_real",
                False,
                ["USE_REAL_LLM"]
            )
        }
