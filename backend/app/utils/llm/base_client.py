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
    def __init__(self, provider: str = "qwen", timeout_seconds: int = 15, max_retries: int = 2):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.api_base = os.getenv("LLM_API_BASE", "")  # 若配置则走真实HTTP接口
        self.default_model = os.getenv("LLM_MODEL", "")
        self.use_real = os.getenv("USE_REAL_LLM", "false").lower() == "true"

    def _mock_token_count(self, prompt: str, completion: str) -> LLMCallCost:
        # 示例：简单按字符数估算为token，真实实现请接入各模型的tokenizer
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(completion) // 4)
        unit_price = 0.002 if self.provider == "deepseek" else 0.003
        return LLMCallCost(prompt_tokens, completion_tokens, unit_price)

    def chat(self, prompt: str, model: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
        # 若配置了真实调用环境，则使用HTTP最小闭环；否则使用占位
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries + 1):
            try:
                start = time.time()
                if self.use_real and self.api_base and self.api_key:
                    # 统一的最小HTTP接口：POST {api_base}/chat
                    # 你可以在网关侧将其映射到Qwen/DeepSeek官方HTTP接口
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
                    # 占位返回
                    completion = "placeholder response"
                elapsed = time.time() - start
                cost = self._mock_token_count(prompt, completion)
                return {
                    "provider": self.provider,
                    "model": model or "auto",
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
        raise RuntimeError(f"LLM request failed: {last_error}")


