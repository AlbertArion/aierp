"""
Agent 权限查询服务
调用 Java 后端 /role/agent-users 接口，获取拥有指定 Agent 权限的用户 ID 列表
"""
import os
import logging
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

# Java 后端网关地址，可通过环境变量 SYSTEM_API_BASE_URL 覆盖
DEFAULT_SYSTEM_BASE_URL = os.getenv("SYSTEM_API_BASE_URL", "http://localhost:9015")
# 通过网关访问时路径带 /api/sinocst-system
AGENT_USERS_PATH = "/api/sinocst-system/role/agent-users"

# 简单内存缓存：agent_name -> (user_ids, timestamp)，缓存 60 秒
_cache: dict = {}
_CACHE_TTL_SEC = 60


def get_agent_authorized_user_ids(agent_name: str, use_cache: bool = True) -> List[str]:
    """
    查询拥有指定 Agent 权限的用户 ID 列表。

    Args:
        agent_name: Agent 标识，如 sd-agent, pp-agent, mm-agent, fi-agent, co-agent
        use_cache: 是否使用缓存

    Returns:
        用户 ID 列表，调用失败时返回空列表
    """
    if not agent_name or not agent_name.strip():
        return []

    if use_cache and agent_name in _cache:
        user_ids, ts = _cache[agent_name]
        import time
        if time.time() - ts < _CACHE_TTL_SEC:
            return user_ids

    url = f"{DEFAULT_SYSTEM_BASE_URL.rstrip('/')}{AGENT_USERS_PATH}"
    params = {"agentName": agent_name.strip()}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning("get_agent_authorized_user_ids status=%s url=%s", resp.status_code, url)
                return []
            data = resp.json()
            # 统一返回格式：{ "code": 200, "data": ["id1", "id2"] }
            if isinstance(data, dict) and data.get("code") == 200:
                user_ids = data.get("data")
                if isinstance(user_ids, list):
                    # 确保为字符串列表（Java 可能返回 Long 的字符串形式）
                    result = [str(uid) for uid in user_ids]
                    if use_cache:
                        import time
                        _cache[agent_name] = (result, time.time())
                    return result
            return []
    except Exception as e:
        logger.exception("get_agent_authorized_user_ids failed: agent_name=%s, error=%s", agent_name, e)
        return []


def is_user_authorized_for_agent(receiver_agent: str, receiver_user_id: Optional[str]) -> bool:
    """
    判断用户是否拥有指定 Agent 的权限。

    Args:
        receiver_agent: Agent 标识
        receiver_user_id: 用户 ID（前端传入的当前用户 ID）

    Returns:
        True 表示有权限；receiver_user_id 为空时视为不按用户过滤（兼容旧逻辑），返回 True
    """
    if not receiver_user_id or not receiver_user_id.strip():
        return True  # 未传用户时不做权限过滤，保持兼容
    allowed = get_agent_authorized_user_ids(receiver_agent, use_cache=True)
    if not allowed:
        # 未配置任何角色拥有该 Agent 时，允许所有用户（兼容未启用权限时的行为）
        return True
    return receiver_user_id.strip() in allowed
