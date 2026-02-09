"""
Agent消息API接口
用于agent之间的消息传递
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import logging
from app.services.agent_message_service import AgentMessageService
from app.services.agent_permission_service import is_user_authorized_for_agent, get_agent_authorized_user_ids

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖注入：创建AgentMessageService实例
def get_message_service() -> AgentMessageService:
    """创建AgentMessageService实例"""
    return AgentMessageService()

# 请求模型
class SendMessageRequest(BaseModel):
    sender_agent: str
    receiver_agent: str
    message_type: str
    content: Dict[str, Any]
    sender_user_id: Optional[str] = None
    receiver_user_id: Optional[str] = None
    """为 True 且未填 receiver_user_id 时，向拥有该接收 agent 权限的所有用户各发一条消息（每人独立已读/已处理）"""
    broadcast_to_authorized: bool = False
    context_id: Optional[str] = None
    conversation_id: Optional[str] = None
    priority: str = "NORMAL"
    mandt: Optional[str] = None
    tenant_id: Optional[str] = None

class ReceiveMessagesRequest(BaseModel):
    receiver_agent: str
    receiver_user_id: Optional[str] = None
    status: str = "PENDING"
    mandt: Optional[str] = None
    conversation_id: Optional[str] = None
    limit: int = 50

@router.post("/agent-message/send")
async def send_message(
    request: SendMessageRequest,
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """
    发送消息
    
    请求体示例:
    {
        "sender_agent": "sd-agent",
        "receiver_agent": "pp-agent",
        "message_type": "PRODUCTION_ORDER_CREATED",
        "content": {
            "action": "CREATE_PRODUCTION_ORDER",
            "data": {
                "vbeln": "0000000123",
                "aufnr": "001010014285",
                "orderType": "production"
            }
        },
        "sender_user_id": "user001",
        "priority": "HIGH",
        "mandt": "600"
    }
    """
    try:
        # 发送给拥有接收 agent 权限的所有用户（每人一条，独立已读/已处理）
        if request.broadcast_to_authorized and not request.receiver_user_id:
            user_ids = get_agent_authorized_user_ids(request.receiver_agent, use_cache=True)
            result = message_service.send_message_to_users(
                sender_agent=request.sender_agent,
                receiver_agent=request.receiver_agent,
                message_type=request.message_type,
                content=request.content,
                receiver_user_ids=user_ids,
                sender_user_id=request.sender_user_id,
                context_id=request.context_id,
                conversation_id=request.conversation_id,
                priority=request.priority,
                mandt=request.mandt,
                tenant_id=request.tenant_id
            )
            return {
                "code": 200,
                "msg": "消息已发送给拥有该 Agent 权限的所有用户",
                "data": result
            }
        result = message_service.send_message(
            sender_agent=request.sender_agent,
            receiver_agent=request.receiver_agent,
            message_type=request.message_type,
            content=request.content,
            sender_user_id=request.sender_user_id,
            receiver_user_id=request.receiver_user_id,
            context_id=request.context_id,
            conversation_id=request.conversation_id,
            priority=request.priority,
            mandt=request.mandt,
            tenant_id=request.tenant_id
        )
        return {
            "code": 200,
            "msg": "消息发送成功",
            "data": result
        }
    except Exception as e:
        logger.error(f"发送消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")

@router.post("/agent-message/receive")
async def receive_messages(
    request: ReceiveMessagesRequest,
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """
    接收消息
    
    请求体示例:
    {
        "receiver_agent": "pp-agent",
        "receiver_user_id": "user001",
        "status": "PENDING",
        "mandt": "600",
        "limit": 50
    }
    """
    if not is_user_authorized_for_agent(request.receiver_agent, request.receiver_user_id):
        return {"code": 200, "msg": "获取消息成功", "data": []}
    try:
        messages = message_service.receive_messages(
            receiver_agent=request.receiver_agent,
            receiver_user_id=request.receiver_user_id,
            status=request.status,
            mandt=request.mandt,
            conversation_id=request.conversation_id,
            limit=request.limit
        )
        
        return {
            "code": 200,
            "msg": "获取消息成功",
            "data": messages
        }
    except Exception as e:
        logger.error(f"接收消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"接收消息失败: {str(e)}")

@router.get("/agent-message/receive")
async def receive_messages_get(
    receiver_agent: str,
    receiver_user_id: Optional[str] = None,
    status: str = "PENDING",
    mandt: Optional[str] = None,
    conversation_id: Optional[str] = None,
    limit: int = 50,
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """
    接收消息（GET方式）
    """
    if not is_user_authorized_for_agent(receiver_agent, receiver_user_id):
        return {"code": 200, "msg": "获取消息成功", "data": []}
    try:
        messages = message_service.receive_messages(
            receiver_agent=receiver_agent,
            receiver_user_id=receiver_user_id,
            status=status,
            mandt=mandt,
            conversation_id=conversation_id,
            limit=limit
        )
        
        return {
            "code": 200,
            "msg": "获取消息成功",
            "data": messages
        }
    except Exception as e:
        logger.error(f"接收消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"接收消息失败: {str(e)}")

@router.post("/agent-message/mark-read")
async def mark_message_read(
    messageId: str = Query(..., alias="messageId"),
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """标记消息为已读"""
    try:
        message_service.mark_message_read(messageId)
        return {
            "code": 200,
            "msg": "消息已标记为已读"
        }
    except Exception as e:
        logger.error(f"标记消息已读失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"标记消息已读失败: {str(e)}")

@router.post("/agent-message/mark-processed")
async def mark_message_processed(
    messageId: str = Query(..., alias="messageId"),
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """标记消息为已处理"""
    try:
        message_service.mark_message_processed(messageId)
        return {
            "code": 200,
            "msg": "消息已标记为已处理"
        }
    except Exception as e:
        logger.error(f"标记消息已处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"标记消息已处理失败: {str(e)}")

@router.get("/agent-message/unread-count")
async def get_unread_count(
    receiver_agent: str,
    receiver_user_id: Optional[str] = None,
    mandt: Optional[str] = None,
    conversation_id: Optional[str] = None,
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """获取未读消息数量"""
    if not is_user_authorized_for_agent(receiver_agent, receiver_user_id):
        return {"code": 200, "msg": "获取未读消息数量成功", "data": {"count": 0}}
    try:
        count = message_service.get_unread_count(
            receiver_agent=receiver_agent,
            receiver_user_id=receiver_user_id,
            mandt=mandt,
            conversation_id=conversation_id
        )
        return {
            "code": 200,
            "msg": "获取未读消息数量成功",
            "data": {
                "count": count
            }
        }
    except Exception as e:
        logger.error(f"获取未读消息数量失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取未读消息数量失败: {str(e)}")

@router.get("/agent-message/conversations")
async def get_conversations(
    receiver_agent: str,
    receiver_user_id: Optional[str] = None,
    mandt: Optional[str] = None,
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """获取有未读消息的对话列表"""
    if not is_user_authorized_for_agent(receiver_agent, receiver_user_id):
        return {"code": 200, "msg": "获取对话列表成功", "data": []}
    try:
        conversations = message_service.get_conversations_with_unread(
            receiver_agent=receiver_agent,
            receiver_user_id=receiver_user_id,
            mandt=mandt
        )
        return {
            "code": 200,
            "msg": "获取对话列表成功",
            "data": conversations
        }
    except Exception as e:
        logger.error(f"获取对话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取对话列表失败: {str(e)}")

@router.get("/agent-message/conversations-with-unread")
async def get_conversations_with_unread(
    receiver_agent: str,
    receiver_user_id: Optional[str] = None,
    mandt: Optional[str] = None,
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """获取有未读消息的对话列表（FI Agent使用）"""
    if not is_user_authorized_for_agent(receiver_agent, receiver_user_id):
        return {"code": 200, "msg": "获取对话列表成功", "data": []}
    try:
        conversations = message_service.get_conversations_with_unread(
            receiver_agent=receiver_agent,
            receiver_user_id=receiver_user_id,
            mandt=mandt
        )
        return {
            "code": 200,
            "msg": "获取对话列表成功",
            "data": conversations
        }
    except Exception as e:
        logger.error(f"获取对话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取对话列表失败: {str(e)}")

@router.get("/agent-message/receive-messages")
async def receive_messages_for_fi(
    receiver_agent: str,
    receiver_user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    status: str = "PENDING",
    mandt: Optional[str] = None,
    limit: int = 50,
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """接收对话消息（FI Agent使用）"""
    if not is_user_authorized_for_agent(receiver_agent, receiver_user_id):
        return {"code": 200, "msg": "获取消息成功", "data": []}
    try:
        messages = message_service.receive_messages(
            receiver_agent=receiver_agent,
            receiver_user_id=receiver_user_id,
            status=status,
            mandt=mandt,
            conversation_id=conversation_id,
            limit=limit
        )
        
        return {
            "code": 200,
            "msg": "获取消息成功",
            "data": messages
        }
    except Exception as e:
        logger.error(f"接收消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"接收消息失败: {str(e)}")

@router.post("/agent-message/mark-read/{message_id}")
async def mark_message_read_by_path(
    message_id: str,
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """标记消息为已读（路径参数方式，FI Agent使用）"""
    try:
        message_service.mark_message_read(message_id)
        return {
            "code": 200,
            "msg": "消息已标记为已读"
        }
    except Exception as e:
        logger.error(f"标记消息已读失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"标记消息已读失败: {str(e)}")

@router.post("/agent-message/mark-processed/{message_id}")
async def mark_message_processed_by_path(
    message_id: str,
    message_service: AgentMessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """标记消息为已处理（路径参数方式，FI Agent使用）"""
    try:
        message_service.mark_message_processed(message_id)
        return {
            "code": 200,
            "msg": "消息已标记为已处理"
        }
    except Exception as e:
        logger.error(f"标记消息已处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"标记消息已处理失败: {str(e)}")

