import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests

# 说明：统一管理Qwen/DeepSeek的API调用，包含超时重试与成本控制（按token计数）


@dataclass
class LLMCallCost:
    prompt_tokens: int
    completion_tokens: int
    unit_price_per_1k_tokens: float

    @property
    def total_cost(self) -> float:
        total_tokens = self.prompt_tokens + self.completion_tokens
        return (total_tokens / 1000.0) * self.unit_price_per_1k_tokens


class LLMClient:
    def __init__(self, provider: str = None, timeout_seconds: int = None, max_retries: int = None):
        """
        初始化LLM客户端
        
        Args:
            provider: 提供商（如果为None，从配置读取）
            timeout_seconds: 超时时间（如果为None，从配置读取）
            max_retries: 最大重试次数（如果为None，从配置读取）
        """
        # 延迟导入避免循环依赖
        from app.services.config_service import ConfigService
        self.config_service = ConfigService()
        
        # 从配置读取或使用传入参数
        self.provider = provider or self.config_service.get_config("llm.provider", "qwen")
        self.timeout_seconds = timeout_seconds or self.config_service.get_config("llm.timeout", 15)
        self.max_retries = max_retries or self.config_service.get_config("llm.max_retries", 2)
        
        # 从配置读取API密钥和Base URL
        self.api_key = self.config_service.get_config("llm.api_key", "")
        if not self.api_key:
            # Fallback到环境变量
            self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
        
        self.api_base = self.config_service.get_config("llm.base_url", "")
        if not self.api_base:
            # Fallback到环境变量
            self.api_base = os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_API_BASE", "")
        
        self.default_model = self.config_service.get_config("llm.model", "")
        if not self.default_model:
            # Fallback到环境变量
            self.default_model = os.getenv("LLM_MODEL", "")
        
        self.use_real = self.config_service.get_config("llm.use_real", False)
        if self.use_real is None:
            # Fallback到环境变量
            self.use_real = os.getenv("USE_REAL_LLM", "false").lower() == "true"

    def _get_unit_price(self) -> float:
        """获取当前提供商的token价格"""
        if self.provider == "deepseek":
            return self.config_service.get_config("llm.unit_price_deepseek", 0.002)
        else:
            return self.config_service.get_config("llm.unit_price_default", 0.003)

    def _mock_token_count(self, prompt: str, completion: str) -> LLMCallCost:
        """估算token数量"""
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(completion) // 4)
        unit_price = self._get_unit_price()
        return LLMCallCost(prompt_tokens, completion_tokens, unit_price)

    def chat(self, prompt: str, model: Optional[str] = None, temperature: float = None) -> Dict[str, Any]:
        """
        调用LLM API
        
        Args:
            prompt: 提示词
            model: 模型名称（如果为None，使用默认模型）
            temperature: 温度参数（如果为None，从配置读取）
        """
        if temperature is None:
            temperature = self.config_service.get_config("llm.temperature", 0.2)
        
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                start = time.time()
                
                if self.use_real and self.api_base and self.api_key:
                    # 使用真实LLM API调用
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "provider": self.provider,
                        "model": model or self.default_model or "auto",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                    }
                    resp = requests.post(
                        f"{self.api_base.rstrip('/')}/chat",
                        json=payload,
                        headers=headers,
                        timeout=self.timeout_seconds,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    completion = data.get("content") or data.get("text") or ""
                else:
                    # 占位返回（用于测试或未配置时）
                    completion = "placeholder response"
                
                elapsed = time.time() - start
                cost = self._mock_token_count(prompt, completion)
                
                return {
                    "provider": self.provider,
                    "model": model or self.default_model or "auto",
                    "prompt": prompt,
                    "completion": completion,
                    "elapsed_seconds": elapsed,
                    "cost": {
                        "prompt_tokens": cost.prompt_tokens,
                        "completion_tokens": cost.completion_tokens,
                        "unit_price_per_1k_tokens": cost.unit_price_per_1k_tokens,
                        "total_cost": round(cost.total_cost, 6),
                    },
                }
            except Exception as e:  # noqa: BLE001
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(1)  # 重试前等待1秒
        
        raise RuntimeError(f"LLM request failed after {self.max_retries + 1} attempts: {last_error}")


