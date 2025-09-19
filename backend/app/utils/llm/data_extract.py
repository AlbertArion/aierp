from .base_client import LLMClient
from typing import Dict, Any

# 说明：非结构化数据转换，调用大模型抽取关键字段


def extract_from_unstructured(content: bytes, filetype: str = "pdf") -> Dict[str, Any]:
    # TODO: 将PDF/Excel解析为文本，然后调用LLM
    client = LLMClient(provider="qwen")
    prompt = "请从以下文本提取关键财务与销售字段，并给出JSON。\n" + content[:200].decode(errors="ignore")
    result = client.chat(prompt)
    return {"raw": result}


