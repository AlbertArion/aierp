# backend/app/repository/work_report_repo.py
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from bson import ObjectId
import logging
import re

logger = logging.getLogger(__name__)

class WorkReportRepository:
    def __init__(self, db):
        self.db = db
        # 兼容不同的数据库类型
        if hasattr(db, 'get_collection'):
            # SQLite数据库
            self.work_reports = db.get_collection('work_reports')
            self.employees = db.get_collection('employees')
            self.projects = db.get_collection('projects')
            self.departments = db.get_collection('departments')
        else:
            # MongoDB或内存数据库
            self.work_reports = db.work_reports
            self.employees = db.employees
            self.projects = db.projects
            self.departments = db.departments
    
    async def search_work_reports(
        self, 
        keyword: Optional[str] = None,
        employee_name: Optional[str] = None,
        project_name: Optional[str] = None,
        department_name: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> Dict[str, Any]:
        """智能搜索报工记录"""
        
        try:
            # 检查数据库类型
            is_sqlite = hasattr(self.work_reports, 'cursor')  # SQLite特征
            is_memory_db = not hasattr(self.work_reports, 'aggregate') and not is_sqlite
            
            if is_sqlite:
                # SQLite数据库 - 使用原生SQL查询
                conditions = []
                params = []
                
                # 关键字搜索（只搜索实际存在的字段）
                if keyword:
                    conditions.append("(work_content LIKE ? OR work_location LIKE ?)")
                    keyword_param = f"%{keyword}%"
                    params.extend([keyword_param, keyword_param])
                
                # 员工姓名过滤（通过JOIN查询）
                if employee_name:
                    conditions.append("e.name LIKE ?")
                    params.append(f"%{employee_name}%")
                    logger.info(f"添加员工名过滤条件: e.name LIKE '%{employee_name}%'")
                
                # 项目名称过滤（通过JOIN查询）
                if project_name:
                    conditions.append("p.project_name LIKE ?")
                    params.append(f"%{project_name}%")
                
                # 部门名称过滤（通过JOIN查询）
                if department_name:
                    conditions.append("d.department_name LIKE ?")
                    params.append(f"%{department_name}%")
                
                # 精确匹配（只使用实际存在的字段）
                if status:
                    conditions.append("status = ?")
                    params.append(status)
                
                # 日期范围
                if start_date:
                    conditions.append("report_date >= ?")
                    params.append(start_date.isoformat())
                if end_date:
                    conditions.append("report_date <= ?")
                    params.append(end_date.isoformat())
                
                # 构建SQL查询
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                # 获取总数（需要JOIN来支持员工名查询）
                count_sql = (
                    "SELECT COUNT(*) FROM work_reports wr "
                    "LEFT JOIN employees e ON wr.employee_id = e.id "
                    "LEFT JOIN projects p ON wr.project_id = p.id "
                    "LEFT JOIN departments d ON wr.department_id = d.id "
                    f"WHERE {where_clause}"
                )
                logger.info("🔍 执行SQLite COUNT查询:")
                logger.info(f"  📝 SQL: {count_sql}")
                logger.info(f"  📊 参数: {params}")
                total = self.work_reports.cursor.execute(count_sql, params).fetchone()[0]
                logger.info(f"  ✅ 查询结果总数: {total}")
                
                # 获取分页数据（带JOIN补充姓名/项目/部门名称）
                skip = (page - 1) * size
                data_sql = (
                    "SELECT wr.*, "
                    "COALESCE(e.name, '未知员工') AS employee_name, "
                    "COALESCE(p.project_name, '未知项目') AS project_name, "
                    "COALESCE(d.department_name, '未知部门') AS department_name "
                    "FROM work_reports wr "
                    "LEFT JOIN employees e ON wr.employee_id = e.id "
                    "LEFT JOIN projects p ON wr.project_id = p.id "
                    "LEFT JOIN departments d ON wr.department_id = d.id "
                    f"WHERE {where_clause} ORDER BY wr.report_date DESC LIMIT ? OFFSET ?"
                )
                params_with_pagination = params + [size, skip]
                
                logger.info("🔍 执行SQLite数据查询:")
                logger.info(f"  📝 SQL: {data_sql}")
                logger.info(f"  📊 参数: {params_with_pagination}")
                
                self.work_reports.cursor.execute(data_sql, params_with_pagination)
                rows = self.work_reports.cursor.fetchall()
                results = [dict(row) for row in rows]
                
                logger.info(f"  ✅ 查询到 {len(results)} 条记录")
                if results:
                    logger.info(f"  📋 前3条记录: {[{'id': r.get('id'), 'employee_name': r.get('employee_name'), 'report_date': r.get('report_date')} for r in results[:3]]}")
                
            elif is_memory_db:
                # 内存数据库 - 使用Python过滤
                all_reports = list(self.work_reports.find())
                
                # 应用过滤条件
                filtered_reports = []
                for report in all_reports:
                    # 关键字搜索
                    if keyword:
                        keyword_lower = keyword.lower()
                        if not any(keyword_lower in str(report.get(field, '')).lower() 
                                  for field in ['work_content', 'employee_name', 'project_name', 'department_name', 'work_location']):
                            continue
                    
                    # 员工姓名过滤
                    if employee_name and employee_name.lower() not in str(report.get('employee_name', '')).lower():
                        continue
                    
                    # 项目名称过滤
                    if project_name and project_name.lower() not in str(report.get('project_name', '')).lower():
                        continue
                    
                    # 部门名称过滤
                    if department_name and department_name.lower() not in str(report.get('department_name', '')).lower():
                        continue
                    
                    # 状态过滤
                    if status and report.get('status') != status:
                        continue
                    
                    # 日期范围过滤
                    if start_date or end_date:
                        report_date = report.get('report_date')
                        if report_date:
                            if isinstance(report_date, str):
                                try:
                                    report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
                                except:
                                    continue
                            elif isinstance(report_date, datetime):
                                report_date = report_date.date()
                            
                            if start_date and report_date < start_date:
                                continue
                            if end_date and report_date > end_date:
                                continue
                    
                    filtered_reports.append(report)
                
                # 排序（按报工日期降序）
                filtered_reports.sort(key=lambda x: x.get('report_date', ''), reverse=True)
                
                # 分页
                total = len(filtered_reports)
                skip = (page - 1) * size
                results = filtered_reports[skip:skip + size]
                
            else:
                # MongoDB - 使用原生查询
                query = {}
                
                # 关键字搜索（全文搜索）
                if keyword:
                    keyword_regex = re.compile(keyword, re.IGNORECASE)
                    query["$or"] = [
                        {"work_content": keyword_regex},
                        {"employee_name": keyword_regex},
                        {"project_name": keyword_regex},
                        {"department_name": keyword_regex},
                        {"work_location": keyword_regex}
                    ]
                
                # 精确匹配
                if employee_name:
                    query["employee_name"] = {"$regex": employee_name, "$options": "i"}
                if project_name:
                    query["project_name"] = {"$regex": project_name, "$options": "i"}
                if department_name:
                    query["department_name"] = {"$regex": department_name, "$options": "i"}
                if status:
                    query["status"] = status
                
                # 日期范围
                if start_date or end_date:
                    date_query = {}
                    if start_date:
                        date_query["$gte"] = start_date
                    if end_date:
                        date_query["$lte"] = end_date
                    query["report_date"] = date_query
                
                total = self.work_reports.count_documents(query)
                skip = (page - 1) * size
                cursor = self.work_reports.find(query).skip(skip).limit(size).sort("report_date", -1)
                results = list(cursor)
            
            # 转换ObjectId为字符串并添加关联信息
            for result in results:
                if "_id" in result:
                    result["id"] = str(result["_id"])
                    del result["_id"]
                
                # 转换日期
                if "report_date" in result and isinstance(result["report_date"], datetime):
                    result["report_date"] = result["report_date"].date()
                if "created_at" in result and isinstance(result["created_at"], datetime):
                    result["created_at"] = result["created_at"]
                if "updated_at" in result and isinstance(result["updated_at"], datetime):
                    result["updated_at"] = result["updated_at"]
                
                # 添加关联信息（如果不存在）
                if not result.get("employee_name"):
                    result["employee_name"] = "未知员工"
                if not result.get("project_name"):
                    result["project_name"] = "未知项目"
                if not result.get("department_name"):
                    result["department_name"] = "未知部门"
            
            return {
                "total": total,
                "page": page,
                "size": size,
                "data": results
            }
            
        except Exception as e:
            logger.error(f"搜索报工记录失败: {e}")
            raise Exception(f"搜索失败: {str(e)}")
    
    async def get_work_report_statistics(self) -> Dict[str, Any]:
        """获取报工统计信息"""
        try:
            # 检查是否是内存数据库
            if hasattr(self.work_reports, 'aggregate'):
                pipeline = [
                    {
                        "$group": {
                            "_id": None,
                            "total_reports": {"$sum": 1},
                            "total_hours": {"$sum": "$work_hours"},
                            "avg_hours": {"$avg": "$work_hours"}
                        }
                    }
                ]
                
                result = list(self.work_reports.aggregate(pipeline))
                return result[0] if result else {
                    "total_reports": 0,
                    "total_hours": 0,
                    "avg_hours": 0
                }
            else:
                # 内存数据库使用Python计算
                all_reports = list(self.work_reports.find())
                total_reports = len(all_reports)
                total_hours = sum(report.get("work_hours", 0) for report in all_reports)
                avg_hours = total_hours / total_reports if total_reports > 0 else 0
                
                return {
                    "total_reports": total_reports,
                    "total_hours": total_hours,
                    "avg_hours": avg_hours
                }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {
                "total_reports": 0,
                "total_hours": 0,
                "avg_hours": 0
            }
    
    async def import_excel_data(self, data: List[Dict]) -> int:
        """导入Excel数据"""
        try:
            # 数据预处理
            processed_data = []
            for item in data:
                # 生成ID
                item_id = str(ObjectId())
                
                # 转换日期格式
                if "report_date" in item and item["report_date"]:
                    if isinstance(item["report_date"], str):
                        try:
                            item["report_date"] = datetime.strptime(item["report_date"], "%Y-%m-%d").date()
                        except:
                            item["report_date"] = datetime.now().date()
                
                # 确保数值类型
                if "work_hours" in item:
                    try:
                        item["work_hours"] = float(item["work_hours"])
                    except:
                        item["work_hours"] = 0.0
                
                # 设置默认值
                item["id"] = item_id
                item["status"] = item.get("status", "pending")
                item["created_at"] = datetime.now()
                item["updated_at"] = datetime.now()
                
                processed_data.append(item)
            
            if processed_data:
                # 检查是否是内存数据库
                if hasattr(self.work_reports, 'insert_many'):
                    result = self.work_reports.insert_many(processed_data)
                    return len(result.inserted_ids)
                else:
                    # 内存数据库使用insert_one
                    count = 0
                    for item in processed_data:
                        self.work_reports.insert_one(item)
                        count += 1
                    return count
            else:
                return 0
                
        except Exception as e:
            logger.error(f"数据导入失败: {e}")
            raise Exception(f"数据导入失败: {str(e)}")
    
    async def create_work_report(self, work_report_data: Dict[str, Any]) -> str:
        """创建报工记录"""
        try:
            work_report_data["id"] = str(ObjectId())
            work_report_data["created_at"] = datetime.now()
            work_report_data["updated_at"] = datetime.now()
            
            result = self.work_reports.insert_one(work_report_data)
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"创建报工记录失败: {e}")
            raise Exception(f"创建失败: {str(e)}")
    
    async def update_work_report(self, report_id: str, update_data: Dict[str, Any]) -> bool:
        """更新报工记录"""
        try:
            update_data["updated_at"] = datetime.now()
            
            result = self.work_reports.update_one(
                {"id": report_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"更新报工记录失败: {e}")
            raise Exception(f"更新失败: {str(e)}")
    
    async def delete_work_report(self, report_id: str) -> bool:
        """删除报工记录"""
        try:
            result = self.work_reports.delete_one({"id": report_id})
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"删除报工记录失败: {e}")
            raise Exception(f"删除失败: {str(e)}")
    
    async def get_work_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取报工记录"""
        try:
            result = self.work_reports.find_one({"id": report_id})
            if result:
                if "_id" in result:
                    result["id"] = str(result["_id"])
                    del result["_id"]
                return result
            return None
            
        except Exception as e:
            logger.error(f"获取报工记录失败: {e}")
            raise Exception(f"获取失败: {str(e)}")
    
    async def create_employee(self, employee_data: Dict[str, Any]) -> str:
        """创建员工信息"""
        try:
            employee_data.setdefault("id", str(ObjectId()))
            employee_data.setdefault("status", "active")
            employee_data["created_at"] = datetime.now()
            employee_data["updated_at"] = datetime.now()
            
            result = self.employees.insert_one(employee_data)
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"创建员工信息失败: {e}")
            raise Exception(f"创建失败: {str(e)}")
    
    async def create_project(self, project_data: Dict[str, Any]) -> str:
        """创建项目信息"""
        try:
            project_data.setdefault("id", str(ObjectId()))
            project_data.setdefault("status", "active")
            project_data["created_at"] = datetime.now()
            project_data["updated_at"] = datetime.now()
            
            result = self.projects.insert_one(project_data)
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"创建项目信息失败: {e}")
            raise Exception(f"创建失败: {str(e)}")
    
    async def create_department(self, department_data: Dict[str, Any]) -> str:
        """创建部门信息"""
        try:
            department_data.setdefault("id", str(ObjectId()))
            department_data.setdefault("status", "active")
            department_data["created_at"] = datetime.now()
            department_data["updated_at"] = datetime.now()
            
            result = self.departments.insert_one(department_data)
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"创建部门信息失败: {e}")
            raise Exception(f"创建失败: {str(e)}")
