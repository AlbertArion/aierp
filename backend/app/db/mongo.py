import os
from typing import Any, Optional
from pymongo import MongoClient

# 说明：MongoDB连接管理器，提供全局client与数据库访问

_client: Optional[MongoClient[Any]] = None


def get_mongo_client() -> MongoClient[Any]:
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        _client = MongoClient(uri)
    return _client


def get_db(db_name: Optional[str] = None):
    name = db_name or os.getenv("MONGO_DB", "aierp")
    return get_mongo_client()[name]


