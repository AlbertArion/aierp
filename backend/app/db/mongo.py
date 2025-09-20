import os
import logging
from typing import Any, Optional, Dict, List
from pymongo import MongoClient

# 说明：MongoDB连接管理器，提供全局client与数据库访问

logger = logging.getLogger(__name__)
_client: Optional[MongoClient[Any]] = None
_memory_db: Optional[Dict[str, Any]] = None

def get_memory_db() -> Dict[str, Any]:
    """获取内存数据库实例"""
    global _memory_db
    if _memory_db is None:
        _memory_db = {
            "process_rules": [],
            "process_alerts": [],
            "users": [],
            "orders": [],
            "predictions": []
        }
    return _memory_db

def get_mongo_client() -> Optional[MongoClient[Any]]:
    global _client
    if _client is None:
        try:
            # 优先使用环境变量配置的MongoDB URI
            uri = os.getenv("MONGO_URI")
            
            if not uri:
                # 直接使用线上MongoDB服务器
                uri = "mongodb://192.144.231.158:27017"
            
            # 设置较长的超时时间，适应网络连接
            _client = MongoClient(uri, serverSelectionTimeoutMS=30000, connectTimeoutMS=30000)
            # 测试连接
            _client.admin.command('ping')
            logger.info(f"MongoDB连接成功: {uri}")
            
        except Exception as e:
            logger.warning(f"MongoDB连接失败: {e}")
            logger.info("使用内存数据库作为fallback")
            _client = None
    
    return _client

def get_db(db_name: Optional[str] = None):
    name = db_name or os.getenv("MONGO_DB", "aierp")
    
    # 如果MongoDB连接失败，使用内存数据库
    client = get_mongo_client()
    if client is None:
        return MemoryDatabase(name)
    
    return client[name]

class MemoryDatabase:
    """内存数据库实现，用于MongoDB连接失败时的fallback"""
    
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.collections = get_memory_db()
    
    def __getitem__(self, collection_name: str):
        return MemoryCollection(collection_name, self.collections)
    
    def __getattr__(self, name):
        return self[name]

class MemoryCollection:
    """内存集合实现"""
    
    def __init__(self, name: str, collections: Dict[str, List[Dict[str, Any]]]):
        self.name = name
        self.data = collections.setdefault(name, [])
        self._id_counter = 1
    
    def find(self, filter_dict: Dict[str, Any] = None, **kwargs):
        """模拟MongoDB find操作"""
        if filter_dict is None:
            filter_dict = {}
        
        result = []
        for item in self.data:
            if self._matches_filter(item, filter_dict):
                result.append(item.copy())
        
        # 处理排序
        if 'sort' in kwargs:
            sort_fields = kwargs['sort']
            for field, direction in reversed(sort_fields):
                result.sort(key=lambda x: x.get(field, ''), reverse=(direction == -1))
        
        # 处理限制
        if 'limit' in kwargs:
            result = result[:kwargs['limit']]
        
        return result
    
    def insert_one(self, document: Dict[str, Any]):
        """模拟MongoDB insert_one操作"""
        doc_copy = document.copy()
        if '_id' not in doc_copy:
            doc_copy['_id'] = f"mem_{self.name}_{self._id_counter}"
            self._id_counter += 1
        self.data.append(doc_copy)
        return type('Result', (), {'inserted_id': doc_copy['_id']})()
    
    def update_one(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]):
        """模拟MongoDB update_one操作"""
        for i, item in enumerate(self.data):
            if self._matches_filter(item, filter_dict):
                if '$set' in update_dict:
                    item.update(update_dict['$set'])
                return type('Result', (), {'modified_count': 1})()
        return type('Result', (), {'modified_count': 0})()
    
    def delete_one(self, filter_dict: Dict[str, Any]):
        """模拟MongoDB delete_one操作"""
        for i, item in enumerate(self.data):
            if self._matches_filter(item, filter_dict):
                self.data.pop(i)
                return type('Result', (), {'deleted_count': 1})()
        return type('Result', (), {'deleted_count': 0})()
    
    def _matches_filter(self, item: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        """检查项目是否匹配过滤器"""
        for key, value in filter_dict.items():
            if key not in item:
                return False
            if item[key] != value:
                return False
        return True


