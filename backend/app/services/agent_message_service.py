"""
Agent消息服务
用于实现agent之间的消息传递
"""
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlite3 import connect, Row
import os

logger = logging.getLogger(__name__)

class AgentMessageService:
    """Agent消息服务"""
    
    def __init__(self):
        # 使用SQLite存储消息（可以后续迁移到PostgreSQL）
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "db", "agent_messages.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建消息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE NOT NULL,
                message_type TEXT NOT NULL,
                sender_agent TEXT NOT NULL,
                sender_user_id TEXT,
                receiver_agent TEXT NOT NULL,
                receiver_user_id TEXT,
                context_id TEXT,
                conversation_id TEXT,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                priority TEXT DEFAULT 'NORMAL',
                mandt TEXT,
                tenant_id TEXT,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_time TIMESTAMP,
                process_time TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        """)
        
        # 添加conversation_id字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE agent_messages ADD COLUMN conversation_id TEXT")
        except:
            pass  # 字段已存在
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_receiver 
            ON agent_messages(receiver_agent, receiver_user_id, status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_message_id 
            ON agent_messages(message_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_context_id 
            ON agent_messages(context_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_id 
            ON agent_messages(conversation_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mandt 
            ON agent_messages(mandt)
        """)
        
        conn.commit()
        conn.close()
    
    def send_message(
        self,
        sender_agent: str,
        receiver_agent: str,
        message_type: str,
        content: Dict[str, Any],
        sender_user_id: Optional[str] = None,
        receiver_user_id: Optional[str] = None,
        context_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        priority: str = "NORMAL",
        mandt: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        发送消息
        
        Args:
            sender_agent: 发送者agent（sd-agent, pp-agent, mm-agent）
            receiver_agent: 接收者agent
            message_type: 消息类型
            content: 消息内容
            sender_user_id: 发送者用户ID
            receiver_user_id: 接收者用户ID
            context_id: 上下文ID（用于关联业务流程）
            conversation_id: 对话ID（如果为None，会自动生成新的对话ID）
            priority: 优先级（HIGH, NORMAL, LOW）
            mandt: 集团号
            tenant_id: 租户ID
        
        Returns:
            包含messageId和conversationId的字典
        """
        message_id = f"MSG_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8].upper()}"
        
        # 如果没有提供conversation_id，生成一个新的对话ID
        if not conversation_id:
            conversation_id = f"CONV_{receiver_agent}_{receiver_user_id or 'ALL'}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
        
        conn = connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO agent_messages 
                (message_id, message_type, sender_agent, sender_user_id, 
                 receiver_agent, receiver_user_id, context_id, conversation_id, content, 
                 priority, mandt, tenant_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id,
                message_type,
                sender_agent,
                sender_user_id,
                receiver_agent,
                receiver_user_id,
                context_id,
                conversation_id,
                json.dumps(content, ensure_ascii=False),
                priority,
                mandt,
                tenant_id,
                "PENDING"
            ))
            
            conn.commit()
            logger.info(f"消息已发送: {message_id}, 从 {sender_agent} 到 {receiver_agent}, 对话ID: {conversation_id}")
            return {
                "messageId": message_id,
                "conversationId": conversation_id
            }
        except Exception as e:
            conn.rollback()
            logger.error(f"发送消息失败: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    
    def receive_messages(
        self,
        receiver_agent: str,
        receiver_user_id: Optional[str] = None,
        status: str = "PENDING",
        mandt: Optional[str] = None,
        conversation_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        接收消息
        
        Args:
            receiver_agent: 接收者agent
            receiver_user_id: 接收者用户ID（可选，如果为None则接收所有发给该agent的消息）
            status: 消息状态（PENDING, PROCESSED）
            mandt: 集团号
            conversation_id: 对话ID（可选，如果提供则只返回该对话的消息）
            limit: 返回消息数量限制
        
        Returns:
            消息列表
        """
        conn = connect(self.db_path)
        conn.row_factory = Row
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT * FROM agent_messages
                WHERE receiver_agent = ? 
                AND status = ?
                AND is_deleted = 0
            """
            params = [receiver_agent, status]
            
            if receiver_user_id:
                query += " AND (receiver_user_id = ? OR receiver_user_id IS NULL)"
                params.append(receiver_user_id)
            
            if mandt:
                query += " AND (mandt = ? OR mandt IS NULL)"
                params.append(mandt)
            
            if conversation_id:
                query += " AND conversation_id = ?"
                params.append(conversation_id)
            
            query += " ORDER BY create_time DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            messages = []
            for row in rows:
                message = {
                    "messageId": row["message_id"],
                    "messageType": row["message_type"],
                    "senderAgent": row["sender_agent"],
                    "senderUserId": row["sender_user_id"],
                    "receiverAgent": row["receiver_agent"],
                    "receiverUserId": row["receiver_user_id"],
                    "contextId": row["context_id"],
                    "conversationId": row["conversation_id"],
                    "content": json.loads(row["content"]),
                    "status": row["status"],
                    "priority": row["priority"],
                    "mandt": row["mandt"],
                    "tenantId": row["tenant_id"],
                    "createTime": row["create_time"],
                    "readTime": row["read_time"],
                    "processTime": row["process_time"]
                }
                messages.append(message)
            
            return messages
        except Exception as e:
            logger.error(f"接收消息失败: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    
    def get_conversations_with_unread(
        self,
        receiver_agent: str,
        receiver_user_id: Optional[str] = None,
        mandt: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取有未读消息的对话列表
        
        Args:
            receiver_agent: 接收者agent
            receiver_user_id: 接收者用户ID
            mandt: 集团号
        
        Returns:
            对话列表，每个对话包含conversationId和未读消息数量
        """
        conn = connect(self.db_path)
        conn.row_factory = Row
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT 
                    conversation_id,
                    COUNT(*) as unread_count,
                    MAX(create_time) as latest_message_time
                FROM agent_messages
                WHERE receiver_agent = ?
                AND status = 'PENDING'
                AND read_time IS NULL
                AND is_deleted = 0
                AND conversation_id IS NOT NULL
            """
            params = [receiver_agent]
            
            if receiver_user_id:
                query += " AND (receiver_user_id = ? OR receiver_user_id IS NULL)"
                params.append(receiver_user_id)
            
            if mandt:
                query += " AND (mandt = ? OR mandt IS NULL)"
                params.append(mandt)
            
            query += " GROUP BY conversation_id ORDER BY latest_message_time DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            conversations = []
            for row in rows:
                conversations.append({
                    "conversationId": row["conversation_id"],
                    "unreadCount": row["unread_count"],
                    "latestMessageTime": row["latest_message_time"]
                })
            
            return conversations
        except Exception as e:
            logger.error(f"获取对话列表失败: {e}", exc_info=True)
            return []
        finally:
            conn.close()
    
    def mark_message_read(self, message_id: str):
        """标记消息为已读"""
        conn = connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE agent_messages
                SET read_time = CURRENT_TIMESTAMP
                WHERE message_id = ?
            """, (message_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"标记消息已读失败: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    
    def mark_message_processed(self, message_id: str):
        """标记消息为已处理"""
        conn = connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE agent_messages
                SET status = 'PROCESSED', process_time = CURRENT_TIMESTAMP
                WHERE message_id = ?
            """, (message_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"标记消息已处理失败: {e}", exc_info=True)
            raise
        finally:
            conn.close()
    
    def get_unread_count(
        self,
        receiver_agent: str,
        receiver_user_id: Optional[str] = None,
        mandt: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> int:
        """获取未读消息数量"""
        conn = connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT COUNT(*) FROM agent_messages
                WHERE receiver_agent = ?
                AND status = 'PENDING'
                AND is_deleted = 0
            """
            params = [receiver_agent]
            
            if receiver_user_id:
                query += " AND (receiver_user_id = ? OR receiver_user_id IS NULL)"
                params.append(receiver_user_id)
            
            if mandt:
                query += " AND (mandt = ? OR mandt IS NULL)"
                params.append(mandt)
            
            if conversation_id:
                query += " AND conversation_id = ?"
                params.append(conversation_id)
            
            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            return count
        except Exception as e:
            logger.error(f"获取未读消息数量失败: {e}", exc_info=True)
            return 0
        finally:
            conn.close()
