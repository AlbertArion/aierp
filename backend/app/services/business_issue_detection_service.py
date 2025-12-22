#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
业务问题识别服务
负责自动识别业务问题并量化问题严重程度
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
from ..db.sqlite_db import get_sqlite_db
from .metric_calculation_service import MetricCalculationService
from ..utils.llm.base_client import LLMClient

logger = logging.getLogger(__name__)


class BusinessIssueDetectionService:
    """业务问题识别服务"""
    
    def __init__(self, token: Optional[str] = None, mandt: Optional[str] = None, tenant_id: Optional[str] = None):
        """
        初始化业务问题识别服务
        
        Args:
            token: 认证token，用于调用Java后端服务
            mandt: 集团代码
            tenant_id: 租户ID
        """
        self.db = get_sqlite_db()
        self.metric_service = MetricCalculationService(token=token, mandt=mandt, tenant_id=tenant_id)
        self.llm_client = LLMClient()
    
    async def detect_issues(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        检测业务问题
        
        Args:
            category: 业务分类(SD/PP/MM/FI/CO)，None表示全部
        
        Returns:
            问题列表
        """
        try:
            # 1. 获取启用的指标定义
            metrics = self._get_enabled_metrics(category)
            
            issues = []
            for metric in metrics:
                # 2. 计算当前指标值
                current_value = await self.metric_service.calculate_metric_value(metric['id'])
                if current_value is None:
                    continue
                
                # 3. 判断是否存在问题
                issue = await self._evaluate_metric_issue(metric, current_value)
                if issue:
                    issues.append(issue)
            
            # 4. 使用AI分析问题严重程度和优先级
            if issues:
                issues = await self._ai_analyze_issues(issues)
            
            # 5. 保存问题记录
            for issue in issues:
                await self._save_issue_record(issue)
            
            return sorted(issues, key=lambda x: x.get('severity_score', 0), reverse=True)
            
        except Exception as e:
            logger.error(f"检测业务问题失败: {e}", exc_info=True)
            return []
    
    def _get_enabled_metrics(self, category: Optional[str] = None) -> List[Dict]:
        """获取启用的指标定义"""
        cursor = self.db.conn.cursor()
        if category:
            cursor.execute('''
                SELECT * FROM biz_metric_definition 
                WHERE is_enabled = 1 AND metric_category = ?
                ORDER BY sort_order
            ''', (category,))
        else:
            cursor.execute('''
                SELECT * FROM biz_metric_definition 
                WHERE is_enabled = 1
                ORDER BY sort_order
            ''')
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def _evaluate_metric_issue(
        self, 
        metric: Dict, 
        current_value: float
    ) -> Optional[Dict[str, Any]]:
        """评估指标是否存在问题"""
        target_value = metric.get('target_value')
        if not target_value:
            return None
        
        target_value = float(target_value)
        deviation = current_value - target_value
        
        # 判断问题严重程度
        critical_threshold = metric.get('critical_threshold')
        warning_threshold = metric.get('warning_threshold')
        
        severity = "info"
        if critical_threshold and abs(deviation) >= float(critical_threshold):
            severity = "critical"
        elif warning_threshold and abs(deviation) >= float(warning_threshold):
            severity = "warning"
        else:
            return None  # 没有问题
        
        # 计算偏差百分比
        if target_value != 0:
            deviation_percent = (deviation / target_value) * 100
        else:
            deviation_percent = 0
        
        return {
            "metric_id": metric['id'],
            "metric_code": metric['metric_code'],
            "metric_name": metric['metric_name'],
            "metric_category": metric['metric_category'],
            "current_value": current_value,
            "target_value": target_value,
            "deviation": deviation,
            "deviation_percent": deviation_percent,
            "severity": severity,
            "unit": metric.get('unit', ''),
            "issue_title": f"{metric['metric_name']}异常",
            "issue_description": f"{metric['metric_name']}当前值为{current_value}{metric.get('unit', '')}，"
                                f"目标值为{target_value}{metric.get('unit', '')}，"
                                f"偏差{deviation:+.2f}{metric.get('unit', '')}"
        }
    
    async def _ai_analyze_issues(self, issues: List[Dict]) -> List[Dict]:
        """使用AI分析问题严重程度"""
        try:
            if not issues:
                return issues
            
            # 构建AI提示词
            issues_summary = "\n".join([
                f"{idx + 1}. {issue['metric_name']} ({issue['metric_code']}): "
                f"当前值={issue['current_value']}{issue.get('unit', '')}, "
                f"目标值={issue['target_value']}{issue.get('unit', '')}, "
                f"偏差={issue['deviation']:+.2f}{issue.get('unit', '')}, "
                f"偏差百分比={issue.get('deviation_percent', 0):+.2f}%"
                for idx, issue in enumerate(issues)
            ])
            
            prompt = f"""你是一个ERP业务分析专家，请分析以下业务指标问题。

问题列表：
{issues_summary}

请为每个问题分析并输出JSON格式（数组形式），包含以下字段：
1. metric_code: 指标代码
2. severity_score: 严重程度评分（1-10，10最严重）
3. issue_title: 优化后的问题标题（更专业、更具体）
4. issue_description: 优化后的问题描述（包含原因分析和影响说明）
5. priority: 优先级（1-10，10最高）

请严格按照以下JSON数组格式输出，不要添加任何其他文字：
[
  {{
    "metric_code": "DSI",
    "severity_score": 9,
    "issue_title": "库存周转天数严重超标",
    "issue_description": "库存周转天数达到118天，超出目标值90天28天（31%），表明库存积压严重，可能影响资金周转和仓储成本。",
    "priority": 9
  }}
]

只输出JSON数组，不要有其他内容。"""
            
            # 调用AI分析
            try:
                ai_result = self.llm_client.chat(prompt, temperature=0.3)
                completion = ai_result.get('completion', '')
                
                # 解析AI返回的JSON
                import json
                import re
                
                # 尝试提取JSON数组
                json_match = re.search(r'\[[\s\S]*\]', completion)
                if json_match:
                    json_str = json_match.group(0)
                    ai_analysis = json.loads(json_str)
                    
                    # 将AI分析结果应用到问题列表
                    analysis_map = {item['metric_code']: item for item in ai_analysis if 'metric_code' in item}
                    
                    for issue in issues:
                        metric_code = issue.get('metric_code')
                        if metric_code in analysis_map:
                            analysis = analysis_map[metric_code]
                            issue['severity_score'] = analysis.get('severity_score', issue.get('severity_score', 5))
                            issue['priority'] = analysis.get('priority', issue.get('priority', 5))
                            if analysis.get('issue_title'):
                                issue['issue_title'] = analysis['issue_title']
                            if analysis.get('issue_description'):
                                issue['issue_description'] = analysis['issue_description']
                        else:
                            # 如果没有AI分析结果，使用默认值
                            self._set_default_issue_scores(issue)
                else:
                    # 如果无法解析JSON，使用默认值
                    logger.warning("AI返回结果无法解析为JSON，使用默认值")
                    for issue in issues:
                        self._set_default_issue_scores(issue)
                        
            except Exception as ai_error:
                logger.warning(f"AI分析调用失败，使用默认值: {ai_error}")
                # AI调用失败时，使用默认值
                for issue in issues:
                    self._set_default_issue_scores(issue)
            
            return issues
            
        except Exception as e:
            logger.error(f"AI分析问题失败: {e}", exc_info=True)
            # 如果AI分析失败，使用默认值
            for issue in issues:
                self._set_default_issue_scores(issue)
            return issues
    
    def _set_default_issue_scores(self, issue: Dict):
        """设置默认的问题评分"""
        if issue['severity'] == 'critical':
            issue['severity_score'] = 9
            issue['priority'] = 9
        elif issue['severity'] == 'warning':
            issue['severity_score'] = 6
            issue['priority'] = 6
        else:
            issue['severity_score'] = 3
            issue['priority'] = 3
    
    async def _save_issue_record(self, issue: Dict):
        """保存问题记录"""
        try:
            cursor = self.db.conn.cursor()
            
            # 检查是否已存在相同的问题
            issue_code = f"{issue['metric_code']}_{datetime.now().strftime('%Y%m%d')}"
            cursor.execute(
                "SELECT id FROM biz_issue_record WHERE issue_code = ? AND status = 'active'",
                (issue_code,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # 更新现有问题
                cursor.execute('''
                    UPDATE biz_issue_record 
                    SET current_value = ?, deviation = ?, severity = ?, severity_score = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    issue['current_value'],
                    issue['deviation'],
                    issue['severity'],
                    issue.get('severity_score', 0),
                    existing['id']
                ))
            else:
                # 创建新问题
                cursor.execute('''
                    INSERT INTO biz_issue_record 
                    (issue_code, metric_id, issue_title, issue_description, severity, 
                     severity_score, current_value, target_value, deviation, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                ''', (
                    issue_code,
                    issue['metric_id'],
                    issue.get('issue_title', ''),
                    issue.get('issue_description', ''),
                    issue['severity'],
                    issue.get('severity_score', 0),
                    issue['current_value'],
                    issue['target_value'],
                    issue['deviation']
                ))
            
            self.db.conn.commit()
            
        except Exception as e:
            logger.error(f"保存问题记录失败: {e}")
    
    async def get_issue_detail(self, issue_id: int) -> Optional[Dict[str, Any]]:
        """获取问题详情"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute('''
                SELECT ir.*, md.metric_name, md.metric_code, md.unit
                FROM biz_issue_record ir
                JOIN biz_metric_definition md ON ir.metric_id = md.id
                WHERE ir.id = ?
            ''', (issue_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            issue = dict(row)
            
            # 获取影响因素
            from .metric_factor_analysis_service import MetricFactorAnalysisService
            factor_service = MetricFactorAnalysisService()
            factors = await factor_service.analyze_factors(issue['metric_id'], {})
            issue['factors'] = factors
            
            # 获取改进措施
            measures = self._get_improvement_measures(issue['metric_id'])
            issue['improvement_measures'] = measures
            
            return issue
            
        except Exception as e:
            logger.error(f"获取问题详情失败: {e}")
            return None
    
    def _get_improvement_measures(self, metric_id: int) -> List[Dict]:
        """获取改进措施"""
        cursor = self.db.conn.cursor()
        cursor.execute('''
            SELECT * FROM biz_improvement_measure
            WHERE metric_id = ? AND is_enabled = 1
            ORDER BY priority DESC
        ''', (metric_id,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def get_ai_recommended_measures(self, issue: Dict) -> List[Dict]:
        """
        使用AI推荐改进措施
        
        Args:
            issue: 问题信息
        
        Returns:
            推荐的改进措施列表
        """
        try:
            prompt = f"""你是一个ERP业务优化专家，请为以下业务问题推荐改进措施。

问题信息：
- 指标名称：{issue.get('metric_name', '')}
- 指标代码：{issue.get('metric_code', '')}
- 当前值：{issue.get('current_value', '')}{issue.get('unit', '')}
- 目标值：{issue.get('target_value', '')}{issue.get('unit', '')}
- 偏差：{issue.get('deviation', 0):+.2f}{issue.get('unit', '')}
- 问题描述：{issue.get('issue_description', '')}

请推荐3-5个具体的改进措施，每个措施包含：
1. measure_name: 措施名称
2. measure_type: 措施类型（如：业务操作、流程优化、系统配置等）
3. expected_improvement: 预期改进效果描述
4. priority: 优先级（1-10）
5. description: 措施详细说明

请以JSON数组格式输出：
[
  {{
    "measure_name": "提升销售速度",
    "measure_type": "业务操作",
    "expected_improvement": "预计可减少DSI 5-8天",
    "priority": 9,
    "description": "通过促销活动、渠道激励等方式加快销售速度，减少库存积压"
  }}
]

只输出JSON数组，不要有其他内容。"""
            
            ai_result = self.llm_client.chat(prompt, temperature=0.5)
            completion = ai_result.get('completion', '')
            
            # 解析JSON
            import json
            import re
            
            json_match = re.search(r'\[[\s\S]*\]', completion)
            if json_match:
                json_str = json_match.group(0)
                recommended_measures = json.loads(json_str)
                return recommended_measures
            else:
                logger.warning("AI推荐的措施无法解析为JSON")
                return []
                
        except Exception as e:
            logger.error(f"AI推荐改进措施失败: {e}", exc_info=True)
            return []

