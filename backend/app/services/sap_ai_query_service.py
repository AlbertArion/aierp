import logging
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date

from app.schemas.sap_ai_query import AIQueryAnalysis, SAPQueryResult
from app.db.sqlite_db import SQLiteDatabase

logger = logging.getLogger(__name__)

class SAPAIQueryService:
    """SAP AI查询服务"""
    
    def __init__(self, db: SQLiteDatabase):
        self.db = db
        
        # 定义查询类型和对应的SQL模板
        self.query_templates = {
            "order_info": """
                SELECT 
                    a.aufnr AS 订单号,
                    a.auart AS 订单类型,
                    a.ernam AS 创建人,
                    DATE(a.erdat) AS 创建日期,
                    a.aenam AS 修改人,
                    a.aedat AS 修改日期,
                    a.ktext AS 订单描述,
                    a.werks AS 工厂,
                    a.bukrs AS 公司代码,
                    a.waers AS 货币,
                    afko.gamng AS 订单数量,
                    afko.gmein AS 订单单位,
                    DATE(afko.gltrp) AS 计划完成日期,
                    afko.gstrp AS 计划开始日期
                FROM aufk a
                LEFT JOIN afko ON a.aufnr = afko.aufnr
                WHERE a.aufnr = '{aufnr}'
            """,
            
            "material_info": """
                SELECT 
                    afpo.aufnr AS 订单号,
                    afpo.posnr AS 项目号,
                    afpo.matnr AS 物料号,
                    makt.maktx AS 物料描述,
                    afpo.psmng AS 计划数量,
                    afpo.wemng AS 确认数量,
                    afpo.iamng AS 已投入数量,
                    afpo.meins AS 单位,
                    afpo.pwerk AS 工厂,
                    afpo.lgort AS 库存地点,
                    CASE 
                        WHEN afpo.psmng > 0 THEN ROUND((afpo.wemng / afpo.psmng) * 100, 2)
                        ELSE 0 
                    END AS 完成百分比
                FROM afpo
                LEFT JOIN makt ON afpo.matnr = makt.matnr AND makt.spras = '1'
                WHERE afpo.aufnr = '{aufnr}'
                ORDER BY afpo.posnr
            """,
            
            "process_info": """
                SELECT 
                    afvc.aufpl AS 订单计划号,
                    afvc.aplzl AS 工序号,
                    afvc.vornr AS 工序编号,
                    afvc.arbid AS 工作中心,
                    afvc.ltxa1 AS 工序描述,
                    afvc.werks AS 工厂,
                    afvc.steus AS 控制码,
                    afvv.meinh AS 时间单位,
                    afvv.vgewi AS 标准时间,
                    afvv.bgewi AS 实际时间
                FROM afvc
                LEFT JOIN afvv ON afvc.aufpl = afvv.aufpl AND afvc.aplzl = afvv.aplzl
                WHERE afvc.aufpl LIKE '{aufnr}%'
                ORDER BY afvc.aplzl
            """,
            
            "status_info": """
                SELECT 
                    jest.objnr AS 对象编号,
                    jest.stat AS 状态码,
                    jest.inact AS 是否激活,
                    jest.chgnr AS 变更号
                FROM jest
                WHERE jest.objnr = (
                    SELECT objnr FROM aufk WHERE aufnr = '{aufnr}'
                )
                ORDER BY jest.stat
            """,
            
            "summary": """
                SELECT 
                    a.aufnr AS 订单号,
                    a.auart AS 订单类型,
                    a.ernam AS 创建人,
                    DATE(a.erdat) AS 创建日期,
                    a.werks AS 工厂,
                    afko.gamng AS 订单数量,
                    afko.gmein AS 订单单位,
                    DATE(afko.gltrp) AS 计划完成日期,
                    afko.gstrp AS 计划开始日期,
                    COUNT(DISTINCT afpo.posnr) AS 物料项目数,
                    COUNT(DISTINCT afvc.aplzl) AS 工序数,
                    COUNT(DISTINCT jest.stat) AS 状态数
                FROM aufk a
                LEFT JOIN afko ON a.aufnr = afko.aufnr
                LEFT JOIN afpo ON a.aufnr = afpo.aufnr
                LEFT JOIN afvc ON afvc.aufpl LIKE a.aufnr || '%'
                LEFT JOIN jest ON a.objnr = jest.objnr
                WHERE a.aufnr = '{aufnr}'
                GROUP BY a.aufnr, a.auart, a.ernam, a.erdat, a.werks, 
                         afko.gamng, afko.gmein, afko.gltrp, afko.gstrp
            """,
            
            "detailed_progress": """
                SELECT DISTINCT
                    a.aufnr AS 订单号,
                    a.auart AS 订单类型,
                    a.ernam AS 创建人,
                    DATE(a.erdat) AS 创建日期,
                    a.werks AS 工厂,
                    afko.gamng AS 订单数量,
                    afko.gmein AS 订单单位,
                    DATE(afko.gltrp) AS 计划完成日期,
                    afpo.posnr AS 项目号,
                    afpo.matnr AS 物料号,
                    makt.maktx AS 物料描述,
                    afpo.psmng AS 计划数量,
                    afpo.wemng AS 确认数量,
                    afpo.iamng AS 已投入数量,
                    CASE 
                        WHEN afpo.psmng > 0 THEN ROUND((afpo.wemng / afpo.psmng) * 100, 2)
                        ELSE 0 
                    END AS 完成百分比,
                    jest.stat AS 状态码
                FROM aufk a
                LEFT JOIN afko ON a.aufnr = afko.aufnr
                LEFT JOIN afpo ON a.aufnr = afpo.aufnr
                LEFT JOIN makt ON afpo.matnr = makt.matnr AND makt.spras = '1'
                LEFT JOIN jest ON jest.objnr = a.objnr AND jest.inact = ''
                WHERE a.aufnr = '{aufnr}'
                ORDER BY afpo.posnr
            """
        }
    
    async def analyze_query(self, query: str) -> AIQueryAnalysis:
        """分析用户查询意图"""
        query_lower = query.lower()
        
        # 提取订单号
        aufnr_pattern = r'(\d{10})'  # 10位数字订单号
        aufnr_match = re.search(aufnr_pattern, query)
        aufnr = aufnr_match.group(1) if aufnr_match else None
        
        # 判断查询类型
        query_type = "detailed_progress"  # 默认查询类型改为详细进度
        confidence = 0.8
        
        if "物料" in query_lower or "材料" in query_lower or "零件" in query_lower:
            query_type = "material_info"
            confidence = 0.9
        elif "工序" in query_lower or "工艺" in query_lower or "步骤" in query_lower:
            query_type = "process_info"
            confidence = 0.9
        elif "状态" in query_lower or "进度" in query_lower:
            query_type = "status_info"
            confidence = 0.9
        elif "基本信息" in query_lower or "订单信息" in query_lower:
            query_type = "order_info"
            confidence = 0.9
        elif "汇总" in query_lower or "统计" in query_lower or "概览" in query_lower:
            query_type = "summary"
            confidence = 0.9
        elif "详细" in query_lower or "完整" in query_lower or "全部" in query_lower:
            query_type = "detailed_progress"
            confidence = 0.9
        
        # 如果没有找到订单号，降低置信度
        if not aufnr:
            confidence = 0.3
        
        return AIQueryAnalysis(
            intent=f"查询订单{aufnr}的{query_type}信息" if aufnr else "查询订单信息",
            queryType=query_type,
            extractedParams={"aufnr": aufnr},
            sqlTemplate=self.query_templates.get(query_type, self.query_templates["summary"]),
            confidence=confidence
        )
    
    async def execute_query(self, analysis: AIQueryAnalysis) -> SAPQueryResult:
        """执行查询并返回结果"""
        try:
            if not analysis.extractedParams.get("aufnr"):
                return SAPQueryResult(
                    explanation="未找到有效的订单号，请提供10位数字的订单号。",
                    rows=[],
                    tableType="sap",
                    sql=None,
                    queryType=analysis.queryType
                )
            
            # 生成SQL语句
            sql = analysis.sqlTemplate.format(**analysis.extractedParams)
            
            # 执行查询
            collection = self.db.get_collection("aufk")  # 使用任意表来执行原始SQL
            rows = self._execute_raw_sql(sql)
            
            # 生成语言描述
            explanation = self._generate_explanation(analysis, rows)
            
            return SAPQueryResult(
                explanation=explanation,
                rows=rows,
                tableType="sap",
                sql=sql,
                queryType=analysis.queryType
            )
            
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            return SAPQueryResult(
                explanation=f"查询执行失败: {str(e)}",
                rows=[],
                tableType="sap",
                sql=None,
                queryType=analysis.queryType
            )
    
    def _execute_raw_sql(self, sql: str) -> List[Dict[str, Any]]:
        """执行原始SQL查询"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            # 转换为字典列表
            columns = [description[0] for description in cursor.description]
            result = []
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    # 处理日期类型
                    if isinstance(value, str) and len(value) == 10 and '-' in value:
                        try:
                            datetime.strptime(value, '%Y-%m-%d')
                            row_dict[columns[i]] = value
                        except ValueError:
                            row_dict[columns[i]] = value
                    else:
                        row_dict[columns[i]] = value
                result.append(row_dict)
            
            return result
            
        except Exception as e:
            logger.error(f"执行SQL失败: {e}")
            return []
    
    def _generate_explanation(self, analysis: AIQueryAnalysis, rows: List[Dict[str, Any]]) -> str:
        """生成查询结果的语言描述"""
        aufnr = analysis.extractedParams.get("aufnr", "未知")
        query_type = analysis.queryType
        
        if not rows:
            return f"未找到订单号 {aufnr} 的相关信息，请确认订单号是否正确。"
        
        explanations = {
            "order_info": f"**订单 {aufnr} 的基本信息：**\n\n",
            "material_info": f"**订单 {aufnr} 的物料信息：**\n\n",
            "process_info": f"**订单 {aufnr} 的工序信息：**\n\n",
            "status_info": f"**订单 {aufnr} 的状态信息：**\n\n",
            "summary": f"**订单 {aufnr} 的汇总信息：**\n\n",
            "detailed_progress": f"**订单 {aufnr} 的详细进度信息：**\n\n"
        }
        
        explanation = explanations.get(query_type, f"**订单 {aufnr} 的查询结果：**\n\n")
        
        # 根据查询类型添加具体描述
        if query_type == "order_info":
            if rows:
                row = rows[0]
                explanation += f"- **订单类型**: {row.get('订单类型', 'N/A')}\n"
                explanation += f"- **创建人**: {row.get('创建人', 'N/A')}\n"
                explanation += f"- **创建日期**: {row.get('创建日期', 'N/A')}\n"
                explanation += f"- **工厂**: {row.get('工厂', 'N/A')}\n"
                explanation += f"- **订单数量**: {row.get('订单数量', 'N/A')} {row.get('订单单位', '')}\n"
                explanation += f"- **计划完成日期**: {row.get('计划完成日期', 'N/A')}\n"
        
        elif query_type == "material_info":
            explanation += f"共找到 **{len(rows)}** 个物料项目：\n\n"
            for i, row in enumerate(rows[:5], 1):  # 只显示前5个
                explanation += f"{i}. **{row.get('物料描述', 'N/A')}** ({row.get('物料号', 'N/A')})\n"
                explanation += f"   - 计划数量: {row.get('计划数量', 'N/A')} {row.get('单位', '')}\n"
                explanation += f"   - 确认数量: {row.get('确认数量', 'N/A')} {row.get('单位', '')}\n"
                explanation += f"   - 完成百分比: {row.get('完成百分比', 'N/A')}%\n\n"
            
            if len(rows) > 5:
                explanation += f"... 还有 {len(rows) - 5} 个物料项目\n\n"
        
        elif query_type == "process_info":
            explanation += f"共找到 **{len(rows)}** 个工序：\n\n"
            for i, row in enumerate(rows[:5], 1):  # 只显示前5个
                explanation += f"{i}. **{row.get('工序描述', 'N/A')}** (工序号: {row.get('工序号', 'N/A')})\n"
                explanation += f"   - 工作中心: {row.get('工作中心', 'N/A')}\n"
                explanation += f"   - 标准时间: {row.get('标准时间', 'N/A')} {row.get('时间单位', '')}\n\n"
            
            if len(rows) > 5:
                explanation += f"... 还有 {len(rows) - 5} 个工序\n\n"
        
        elif query_type == "status_info":
            active_statuses = [row for row in rows if not row.get('是否激活')]
            explanation += f"共找到 **{len(rows)}** 个状态，其中 **{len(active_statuses)}** 个为激活状态：\n\n"
            for row in active_statuses[:5]:
                explanation += f"- 状态码: {row.get('状态码', 'N/A')}\n"
        
        elif query_type == "summary":
            if rows:
                row = rows[0]
                explanation += f"- **订单类型**: {row.get('订单类型', 'N/A')}\n"
                explanation += f"- **创建人**: {row.get('创建人', 'N/A')}\n"
                explanation += f"- **工厂**: {row.get('工厂', 'N/A')}\n"
                explanation += f"- **物料项目数**: {row.get('物料项目数', 'N/A')}\n"
                explanation += f"- **工序数**: {row.get('工序数', 'N/A')}\n"
                explanation += f"- **状态数**: {row.get('状态数', 'N/A')}\n"
        
        elif query_type == "detailed_progress":
            explanation += f"**详细进度信息** (共 {len(rows)} 条记录)：\n\n"
            explanation += "包含物料信息、工序信息和完成进度等详细信息。\n"
            
            # 检查是否有工序信息
            has_process_info = any(row.get('工序号') is not None or row.get('工序描述') is not None for row in rows)
            if not has_process_info:
                explanation += "\n⚠️ **注意**: 该订单暂无工序信息，可能原因：\n"
                explanation += "- 订单尚未开始生产\n"
                explanation += "- 工序数据尚未录入系统\n"
                explanation += "- 该订单类型不需要工序信息\n"
        
        return explanation
    
    async def process_query(self, query: str) -> SAPQueryResult:
        """处理用户查询的完整流程"""
        # 1. 分析查询意图
        analysis = await self.analyze_query(query)
        
        # 2. 执行查询
        result = await self.execute_query(analysis)
        
        return result
