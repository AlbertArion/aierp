"""
核价数据访问层
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import json

from ..schemas.pricing import (
    MaterialData, PricingResult, PricingStatistics, 
    PricingRule, PricingHistory, ComplexityLevel, PricingStatus
)
from ..db.mongo import get_db

logger = logging.getLogger(__name__)


class PricingRepository:
    """核价数据访问层"""
    
    def __init__(self):
        self.db = get_db()
        # 兼容不同的数据库类型
        if hasattr(self.db, '__getitem__'):
            # MongoDB或Memory数据库
            self.materials_collection = self.db["materials"]
            self.pricing_results_collection = self.db["pricing_results"]
            self.pricing_rules_collection = self.db["pricing_rules"]
            self.pricing_history_collection = self.db["pricing_history"]
        else:
            # SQLite数据库
            from ..db.sqlite_db import SQLiteCollection
            self.materials_collection = SQLiteCollection(self.db.conn, "materials")
            self.pricing_results_collection = SQLiteCollection(self.db.conn, "pricing_results")
            self.pricing_rules_collection = SQLiteCollection(self.db.conn, "pricing_rules")
            self.pricing_history_collection = SQLiteCollection(self.db.conn, "pricing_history")
    
    async def create_material(self, material: MaterialData) -> MaterialData:
        """创建物料数据"""
        try:
            material_dict = material.dict()
            material_dict["id"] = str(uuid.uuid4())
            material_dict["created_at"] = datetime.now()
            material_dict["updated_at"] = datetime.now()
            
            if hasattr(self.materials_collection, 'insert_one'):
                # MongoDB
                result = self.materials_collection.insert_one(material_dict)
                material_dict["id"] = str(result.inserted_id)
            else:
                # Memory database
                self.materials_collection.insert_one(material_dict)
            
            return MaterialData(**material_dict)
        except Exception as e:
            logger.error(f"创建物料数据失败: {e}")
            raise
    
    async def get_materials(self, skip: int = 0, limit: int = 100) -> List[MaterialData]:
        """获取物料列表"""
        try:
            cursor = self.materials_collection.find().skip(skip).limit(limit)
            materials = []
            
            if hasattr(cursor, 'to_list'):
                # MongoDB
                docs = await cursor.to_list(length=limit)
            else:
                # Memory database
                docs = list(cursor)
            
            for doc in docs:
                materials.append(MaterialData(**doc))
            
            return materials
        except Exception as e:
            logger.error(f"获取物料列表失败: {e}")
            return []
    
    async def create_pricing_result(self, result: PricingResult) -> PricingResult:
        """创建核价结果"""
        try:
            result_dict = result.dict()
            result_dict["id"] = str(uuid.uuid4())
            result_dict["created_at"] = datetime.now()
            result_dict["updated_at"] = datetime.now()
            
            if hasattr(self.pricing_results_collection, 'insert_one'):
                # MongoDB
                db_result = self.pricing_results_collection.insert_one(result_dict)
                result_dict["id"] = str(db_result.inserted_id)
            else:
                # Memory database
                self.pricing_results_collection.insert_one(result_dict)
            
            return PricingResult(**result_dict)
        except Exception as e:
            logger.error(f"创建核价结果失败: {e}")
            raise
    
    async def batch_create_pricing_results(self, results: List[PricingResult]) -> List[PricingResult]:
        """批量创建核价结果"""
        try:
            result_dicts = []
            for result in results:
                result_dict = result.dict()
                result_dict["id"] = str(uuid.uuid4())
                result_dict["created_at"] = datetime.now()
                result_dict["updated_at"] = datetime.now()
                result_dicts.append(result_dict)
            
            if hasattr(self.pricing_results_collection, 'insert_many'):
                # MongoDB
                db_results = self.pricing_results_collection.insert_many(result_dicts)
                for i, result_dict in enumerate(result_dicts):
                    result_dict["id"] = str(db_results.inserted_ids[i])
            else:
                # Memory database
                for result_dict in result_dicts:
                    self.pricing_results_collection.insert_one(result_dict)
            
            return [PricingResult(**rd) for rd in result_dicts]
        except Exception as e:
            logger.error(f"批量创建核价结果失败: {e}")
            raise
    
    async def get_pricing_results(self, skip: int = 0, limit: int = 100, status: Optional[PricingStatus] = None) -> List[PricingResult]:
        """获取核价结果列表"""
        try:
            query = {}
            if status:
                query["status"] = status.value
            
            cursor = self.pricing_results_collection.find(query).skip(skip).limit(limit)
            
            if hasattr(cursor, 'to_list'):
                # MongoDB
                docs = await cursor.to_list(length=limit)
            else:
                # Memory database
                docs = list(cursor)
            
            results = []
            for doc in docs:
                results.append(PricingResult(**doc))
            
            return results
        except Exception as e:
            logger.error(f"获取核价结果失败: {e}")
            return []
    
    async def update_pricing_result_status(self, result_id: str, status: PricingStatus, approved_by: str = None) -> bool:
        """更新核价结果状态"""
        try:
            update_data = {
                "status": status.value,
                "updated_at": datetime.now()
            }
            
            if status == PricingStatus.APPROVED:
                update_data["approval_time"] = datetime.now()
                if approved_by:
                    update_data["approved_by"] = approved_by
            
            if hasattr(self.pricing_results_collection, 'update_one'):
                # MongoDB
                result = self.pricing_results_collection.update_one(
                    {"id": result_id}, 
                    {"$set": update_data}
                )
                return result.modified_count > 0
            else:
                # Memory database
                self.pricing_results_collection.update_one(
                    {"id": result_id}, 
                    {"$set": update_data}
                )
                return True
        except Exception as e:
            logger.error(f"更新核价结果状态失败: {e}")
            return False
    
    async def get_pricing_statistics(self) -> PricingStatistics:
        """获取核价统计信息"""
        try:
            total_materials = self.pricing_results_collection.count_documents({})
            approved_count = self.pricing_results_collection.count_documents({"status": "approved"})
            pending_count = self.pricing_results_collection.count_documents({"status": "pending"})
            rejected_count = self.pricing_results_collection.count_documents({"status": "rejected"})
            
            # 计算总节省成本和平均成本差异
            pipeline = [
                {"$match": {"status": "approved"}},
                {"$group": {
                    "_id": None,
                    "total_savings": {"$sum": {"$abs": "$cost_difference"}},
                    "avg_difference": {"$avg": "$cost_difference"},
                    "count": {"$sum": 1}
                }}
            ]
            
            if hasattr(self.pricing_results_collection, 'aggregate'):
                # MongoDB
                agg_result = list(self.pricing_results_collection.aggregate(pipeline))
            else:
                # Memory database - 简化计算
                approved_results = list(self.pricing_results_collection.find({"status": "approved"}))
                total_savings = sum(abs(r.get("cost_difference", 0)) for r in approved_results)
                avg_difference = sum(r.get("cost_difference", 0) for r in approved_results) / len(approved_results) if approved_results else 0
                agg_result = [{"total_savings": total_savings, "avg_difference": avg_difference, "count": len(approved_results)}]
            
            total_savings = agg_result[0]["total_savings"] if agg_result else 0
            avg_cost_difference = agg_result[0]["avg_difference"] if agg_result else 0
            
            return PricingStatistics(
                total_materials=total_materials,
                approved_count=approved_count,
                pending_count=pending_count,
                rejected_count=rejected_count,
                total_savings=total_savings,
                avg_cost_difference=avg_cost_difference
            )
        except Exception as e:
            logger.error(f"获取核价统计信息失败: {e}")
            return PricingStatistics(
                total_materials=0,
                approved_count=0,
                pending_count=0,
                rejected_count=0,
                total_savings=0.0,
                avg_cost_difference=0.0
            )
    
    async def create_pricing_rule(self, rule: PricingRule) -> PricingRule:
        """创建核价规则"""
        try:
            rule_dict = rule.dict()
            rule_dict["id"] = str(uuid.uuid4())
            rule_dict["created_at"] = datetime.now()
            rule_dict["updated_at"] = datetime.now()
            
            if hasattr(self.pricing_rules_collection, 'insert_one'):
                # MongoDB
                result = self.pricing_rules_collection.insert_one(rule_dict)
                rule_dict["id"] = str(result.inserted_id)
            else:
                # Memory database
                self.pricing_rules_collection.insert_one(rule_dict)
            
            return PricingRule(**rule_dict)
        except Exception as e:
            logger.error(f"创建核价规则失败: {e}")
            raise
    
    async def get_pricing_rules(self) -> List[PricingRule]:
        """获取核价规则列表"""
        try:
            cursor = self.pricing_rules_collection.find({"is_active": True})
            
            if hasattr(cursor, 'to_list'):
                # MongoDB
                docs = await cursor.to_list(length=None)
            else:
                # Memory database
                docs = list(cursor)
            
            rules = []
            for doc in docs:
                rules.append(PricingRule(**doc))
            
            return rules
        except Exception as e:
            logger.error(f"获取核价规则失败: {e}")
            return []
    
    async def save_pricing_history(self, history: PricingHistory) -> PricingHistory:
        """保存核价历史记录"""
        try:
            history_dict = history.dict()
            history_dict["id"] = str(uuid.uuid4())
            history_dict["created_at"] = datetime.now()
            
            if hasattr(self.pricing_history_collection, 'insert_one'):
                # MongoDB
                result = self.pricing_history_collection.insert_one(history_dict)
                history_dict["id"] = str(result.inserted_id)
            else:
                # Memory database
                self.pricing_history_collection.insert_one(history_dict)
            
            return PricingHistory(**history_dict)
        except Exception as e:
            logger.error(f"保存核价历史失败: {e}")
            raise
    
    async def batch_update_pricing_status(self, result_ids: List[str], status: PricingStatus, approved_by: str = None) -> int:
        """批量更新核价结果状态"""
        try:
            update_data = {
                "status": status.value,
                "updated_at": datetime.now()
            }
            
            if status == PricingStatus.APPROVED:
                update_data["approval_time"] = datetime.now()
                if approved_by:
                    update_data["approved_by"] = approved_by
            
            if hasattr(self.pricing_results_collection, 'update_many'):
                # MongoDB
                result = self.pricing_results_collection.update_many(
                    {"id": {"$in": result_ids}}, 
                    {"$set": update_data}
                )
                return result.modified_count
            else:
                # Memory database
                updated_count = 0
                for result_id in result_ids:
                    self.pricing_results_collection.update_one(
                        {"id": result_id}, 
                        {"$set": update_data}
                    )
                    updated_count += 1
                return updated_count
        except Exception as e:
            logger.error(f"批量更新核价结果状态失败: {e}")
            return 0
    
    async def search_materials(
        self, 
        material_name: Optional[str] = None,
        specification: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20
    ) -> List[MaterialData]:
        """搜索物料数据"""
        try:
            query = {}
            
            # 构建查询条件
            if material_name:
                query["material_name"] = {"$regex": material_name, "$options": "i"}
            
            if specification:
                query["specification"] = {"$regex": specification, "$options": "i"}
            
            if keyword:
                # 关键词搜索：在物料名称、规格、工艺要求中搜索
                query["$or"] = [
                    {"material_name": {"$regex": keyword, "$options": "i"}},
                    {"specification": {"$regex": keyword, "$options": "i"}},
                    {"process_requirements": {"$regex": keyword, "$options": "i"}}
                ]
            
            # 执行查询
            if hasattr(self.materials_collection, 'find'):
                # MongoDB
                cursor = self.materials_collection.find(query).limit(limit)
                materials = []
                for doc in cursor:
                    # 转换MongoDB文档为MaterialData对象
                    doc["id"] = str(doc.get("_id", doc.get("id")))
                    materials.append(MaterialData(**doc))
                return materials
            else:
                # Memory数据库或SQLite
                all_materials = self.materials_collection.find(query)
                materials = []
                count = 0
                for doc in all_materials:
                    if count >= limit:
                        break
                    materials.append(MaterialData(**doc))
                    count += 1
                return materials
                
        except Exception as e:
            logger.error(f"搜索物料数据失败: {e}")
            return []