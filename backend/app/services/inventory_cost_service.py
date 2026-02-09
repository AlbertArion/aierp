#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
库存成本分析服务
通过调用 Java ERP 后端 API 获取真实库存数据，计算 7 个核心指标，
并基于真实数据进行根因分析。
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from ..services.erp_service_client import ERPServiceClient
from ..db.sqlite_db import get_sqlite_db

logger = logging.getLogger(__name__)


class InventoryCostService:
    """库存成本分析服务"""

    # 指标目标值（可以后续从配置表读取）
    METRIC_TARGETS = {
        "ENDING_INVENTORY_VALUE": {"target": 2400, "unit": "万元", "direction": "lower_is_better"},
        "INVENTORY_TURNOVER": {"target": 4.0, "unit": "次/年", "direction": "higher_is_better"},
        "SALES_INVENTORY_RATIO": {"target": 85, "unit": "%", "direction": "higher_is_better"},
        "DSI": {"target": 90, "unit": "天", "direction": "lower_is_better"},
        "OBSOLETE_INVENTORY_RATIO": {"target": 10, "unit": "%", "direction": "lower_is_better"},
        "SHORTAGE_RATE": {"target": 3, "unit": "%", "direction": "lower_is_better"},
        "FORECAST_ACCURACY": {"target": 85, "unit": "%", "direction": "higher_is_better"},
    }

    def __init__(self, token: str = None, mandt: str = None, tenant_id: str = None):
        self.erp_client = ERPServiceClient(token=token, mandt=mandt, tenant_id=tenant_id)
        self.db = get_sqlite_db()
        self._ensure_tables()

    def _ensure_tables(self):
        """确保快照表存在"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inventory_cost_metric_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT NOT NULL,
                    metric_code TEXT NOT NULL,
                    metric_value REAL,
                    target_value REAL,
                    unit TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(snapshot_date, metric_code)
                )
            ''')
            self.db.conn.commit()
        except Exception as e:
            logger.warning(f"创建快照表失败: {e}")

    # ========== 数据获取方法 ==========

    async def fetch_inventory_report(self) -> Optional[Dict]:
        """
        获取最新的库存报表数据（来自 WM 模块 InventoryReportController）
        包含: turnoverRate, turnoverDays, totalValue, slowMovingCount, aging buckets 等
        """
        try:
            result = await self.erp_client._request(
                "sinocst-module-wm",
                "GET",
                "/inventory-report/page",
                params={"current": 1, "size": 1, "descs": "report_date"}
            )
            records = result.get("data", {}).get("records", [])
            if records:
                return records[0]
            return None
        except Exception as e:
            logger.warning(f"获取库存报表失败: {e}")
            return None

    async def fetch_inventory_valuation(self) -> List[Dict]:
        """
        获取物料估值数据（来自 MasterData MBEW 表）
        注意：Java ERP 中 salk3=-1 表示空值，需用 stprs*lbkum 计算
        """
        try:
            result = await self.erp_client._request(
                "sinocst-master-data",
                "GET",
                "/sinocst-mbew/mbew/list",
                params={"current": 1, "size": 9999}
            )
            records = result.get("data", {}).get("records", [])
            logger.info(f"获取到 {len(records)} 条物料估值记录")
            return records
        except Exception as e:
            logger.warning(f"获取物料估值数据失败: {e}")
            return []

    async def fetch_material_movements(self, days: int = 90) -> List[Dict]:
        """
        获取物料移动数据（来自 MSEG 表，通过 MasterData 模块）
        优先使用轻量接口 /list-simple（无 N+1）；若 404 则降级到 /list
        注意：dmbtr=-1 表示空值，menge 是字符串
        """
        import asyncio

        async def _fetch_pages(base_path: str) -> List[Dict]:
            out = []
            result = await self.erp_client._request(
                "sinocst-master-data", "GET", base_path,
                params={"current": 1, "size": 200}
            )
            page_data = result.get("data", {})
            out.extend(page_data.get("records", []))
            total = int(page_data.get("total", 0))
            pages = min((total + 199) // 200, 3)
            if pages > 1:
                tasks = [
                    self.erp_client._request(
                        "sinocst-master-data", "GET", base_path,
                        params={"current": p, "size": 200}
                    )
                    for p in range(2, pages + 1)
                ]
                for pr in await asyncio.gather(*tasks, return_exceptions=True):
                    if not isinstance(pr, Exception):
                        out.extend(pr.get("data", {}).get("records", []))
            return out

        path_simple = "/sinocst-mseg/mseg/list-simple"
        path_list = "/sinocst-mseg/mseg/list"
        try:
            all_records = await _fetch_pages(path_simple)
            logger.info(f"获取到 {len(all_records)} 条物料移动记录 (list-simple)")
            return all_records
        except Exception as e:
            if "404" in str(e) or "Not Found" in str(e):
                logger.info("list-simple 不可用，降级到 list")
                try:
                    all_records = await _fetch_pages(path_list)
                    logger.info(f"获取到 {len(all_records)} 条物料移动记录 (list)")
                    return all_records
                except Exception as e2:
                    logger.warning(f"获取物料移动数据失败: {e2}")
                    return []
            logger.warning(f"获取物料移动数据失败: {e}")
            return []

    async def fetch_sales_data(self, days: int = 90) -> List[Dict]:
        """
        获取销售订单行项目数据（来自 SD 模块 VBAP 表）
        注意：VBRP/VBRK 发票端点不可用，改用 VBAP 销售订单行
        """
        try:
            result = await self.erp_client._request(
                "sinocst-module-sd",
                "GET",
                "/sinocst-vbap/vbap/list",
                params={
                    "current": 1,
                    "size": 500,
                }
            )
            records = result.get("data", {}).get("records", [])
            logger.info(f"获取到 {len(records)} 条销售订单行记录")
            return records
        except Exception as e:
            logger.warning(f"获取销售订单数据失败: {e}")
            return []

    async def fetch_reservations(self) -> List[Dict]:
        """
        获取物料预留数据（来自 PP 模块 RESB 表）
        注意：bdmng/enmng 是字符串格式 (如 "1.000")
        """
        try:
            result = await self.erp_client._request(
                "sinocst-module-pp",
                "GET",
                "/sinocst-resb/resb/list",
                params={"current": 1, "size": 9999}
            )
            records = result.get("data", {}).get("records", [])
            logger.info(f"获取到 {len(records)} 条物料预留记录")
            return records
        except Exception as e:
            logger.warning(f"获取物料预留数据失败: {e}")
            return []

    async def fetch_inventory_stock(self) -> List[Dict]:
        """
        获取当前库存数据（来自 WM 模块 MARD 表）
        端点：/sinocst-mard/mard/list
        """
        try:
            result = await self.erp_client._request(
                "sinocst-module-wm",
                "GET",
                "/sinocst-mard/mard/list",
                params={"current": 1, "size": 9999}
            )
            records = result.get("data", {}).get("records", [])
            logger.info(f"获取到 {len(records)} 条库存记录")
            return records
        except Exception as e:
            logger.warning(f"获取库存数据失败: {e}")
            return []

    # ========== 数据辅助方法 ==========

    @staticmethod
    def _safe_float(value, default=0.0) -> float:
        """
        安全转换数值，Java ERP 用 -1 表示空值，字符串需转换
        """
        if value is None:
            return default
        try:
            f = float(value)
            return default if f == -1 else f
        except (ValueError, TypeError):
            return default

    def _get_material_price_map(self, valuations: List[Dict]) -> Dict[str, float]:
        """
        从 MBEW 数据构建物料→单价映射
        优先用 verpr (移动平均价)，其次 stprs (标准价)
        """
        price_map = {}
        for v in valuations:
            matnr = v.get("matnr", "")
            if not matnr:
                continue
            verpr = self._safe_float(v.get("verpr"))
            stprs = self._safe_float(v.get("stprs"))
            price = verpr if verpr > 0 else stprs
            if price > 0 and (matnr not in price_map or price > price_map[matnr]):
                price_map[matnr] = price
        return price_map

    # ========== 指标计算方法 ==========

    async def calculate_all_metrics(self) -> List[Dict]:
        """
        计算所有 7 个库存成本指标的真实值
        
        Returns:
            指标列表，每个指标包含 metric_code, metric_name, unit, current_value, 
            target_value, severity, deviation
        """
        # 并行获取所有数据源
        import asyncio

        (
            inventory_report,
            valuations,
            movements,
            sales_data,
            reservations,
            stock_data,
        ) = await asyncio.gather(
            self.fetch_inventory_report(),
            self.fetch_inventory_valuation(),
            self.fetch_material_movements(days=180),
            self.fetch_sales_data(days=90),
            self.fetch_reservations(),
            self.fetch_inventory_stock(),
            return_exceptions=True,
        )

        # 容错处理：如果某个任务异常，设为空
        if isinstance(inventory_report, Exception):
            logger.warning(f"库存报表获取异常: {inventory_report}")
            inventory_report = None
        if isinstance(valuations, Exception):
            logger.warning(f"物料估值获取异常: {valuations}")
            valuations = []
        if isinstance(movements, Exception):
            logger.warning(f"物料移动获取异常: {movements}")
            movements = []
        if isinstance(sales_data, Exception):
            logger.warning(f"销售数据获取异常: {sales_data}")
            sales_data = []
        if isinstance(reservations, Exception):
            logger.warning(f"物料预留获取异常: {reservations}")
            reservations = []
        if isinstance(stock_data, Exception):
            logger.warning(f"库存数据获取异常: {stock_data}")
            stock_data = []

        logger.info(f"数据源概况: 估值={len(valuations)}条, 移动={len(movements)}条, "
                     f"销售={len(sales_data)}条, 预留={len(reservations)}条, 库存={len(stock_data)}条")

        metrics = []

        # 1. 期末库存金额 (万元)
        ending_inv_value = self._calc_ending_inventory_value(valuations, inventory_report)
        metrics.append(self._build_metric("ENDING_INVENTORY_VALUE", "期末库存金额", ending_inv_value))

        # 2. 库存周转率 (次/年)
        turnover = self._calc_inventory_turnover(movements, valuations, inventory_report)
        metrics.append(self._build_metric("INVENTORY_TURNOVER", "库存周转率", turnover))

        # 3. 销存比 (%)
        sales_inv_ratio = self._calc_sales_inventory_ratio(sales_data, valuations, ending_inv_value)
        metrics.append(self._build_metric("SALES_INVENTORY_RATIO", "销存比", sales_inv_ratio))

        # 4. DSI 库存天数
        dsi = self._calc_dsi(turnover, inventory_report)
        metrics.append(self._build_metric("DSI", "DSI (库存天数)", dsi))

        # 5. 呆滞库存占比 (%)
        obsolete_ratio = self._calc_obsolete_ratio(movements, stock_data, inventory_report)
        metrics.append(self._build_metric("OBSOLETE_INVENTORY_RATIO", "呆滞库存占比", obsolete_ratio))

        # 6. 缺料率 (%)
        shortage = self._calc_shortage_rate(reservations, stock_data)
        metrics.append(self._build_metric("SHORTAGE_RATE", "缺料率", shortage))

        # 7. 需求预测准确率 (%)
        forecast_acc = self._calc_forecast_accuracy(reservations, movements)
        metrics.append(self._build_metric("FORECAST_ACCURACY", "需求预测准确率", forecast_acc))

        # 保存快照
        self._save_snapshot(metrics)

        return metrics

    def _calc_ending_inventory_value(self, valuations: List[Dict], report: Optional[Dict]) -> Optional[float]:
        """
        计算期末库存金额（万元）
        Java ERP 中 salk3 全为 -1（空值），改用 stprs * lbkum
        """
        # 优先从库存报表获取
        if report:
            tv = self._safe_float(report.get("totalValue"))
            if tv > 0:
                return round(tv / 10000, 2)

        # 从 MBEW 汇总：stprs(标准价) * lbkum(库存量)，跳过无效值
        if valuations:
            total = 0.0
            for v in valuations:
                stprs = self._safe_float(v.get("stprs"))
                lbkum = self._safe_float(v.get("lbkum"))
                verpr = self._safe_float(v.get("verpr"))
                # 优先用移动平均价，其次标准价
                price = verpr if verpr > 0 else stprs
                if price > 0 and lbkum > 0:
                    total += price * lbkum
            if total > 0:
                return round(total / 10000, 2)

        return None

    def _calc_inventory_turnover(self, movements: List[Dict], valuations: List[Dict], report: Optional[Dict]) -> Optional[float]:
        """
        计算库存周转率（次/年）
        COGS = 消耗移动(261/601)的 menge * 物料单价
        dmbtr 在 Java ERP 中为 -1，改用 menge * price
        """
        # 优先从库存报表获取
        if report:
            tr = self._safe_float(report.get("turnoverRate"))
            if tr > 0:
                return round(tr, 2)

        # 构建物料单价映射
        price_map = self._get_material_price_map(valuations)

        # 从 MSEG 消耗移动计算 COGS
        consumption_types = {"261", "601"}
        cogs = 0.0
        movement_days = set()
        for m in movements:
            bwart = str(m.get("bwart", ""))
            if bwart in consumption_types:
                matnr = m.get("matnr", "")
                menge = self._safe_float(m.get("menge"))
                price = price_map.get(matnr, 0)
                if menge > 0 and price > 0:
                    cogs += menge * price
                # 记录日期以计算天数范围
                budat = m.get("budat_mkpf") or m.get("budat", "")
                if budat:
                    movement_days.add(budat)

        if cogs > 0:
            # 计算数据覆盖的天数（用于年化）
            if len(movement_days) >= 2:
                days_span = max(180, len(movement_days))  # 至少按180天算
            else:
                days_span = 180
            annual_cogs = cogs * (365 / days_span)

            # 平均库存：用 stprs * lbkum 计算
            avg_inv = 0.0
            for v in valuations:
                stprs = self._safe_float(v.get("stprs"))
                lbkum = self._safe_float(v.get("lbkum"))
                verpr = self._safe_float(v.get("verpr"))
                price = verpr if verpr > 0 else stprs
                if price > 0 and lbkum > 0:
                    avg_inv += price * lbkum

            if avg_inv > 0:
                return round(annual_cogs / avg_inv, 2)

        return None

    def _calc_sales_inventory_ratio(self, sales: List[Dict], valuations: List[Dict], ending_inv: Optional[float]) -> Optional[float]:
        """
        计算销存比（%）= 期间销售额 / 库存金额 × 100
        使用 VBAP.netwr，跳过 -1 空值
        """
        total_sales = sum(self._safe_float(s.get("netwr")) for s in sales)
        if total_sales > 0 and ending_inv and ending_inv > 0:
            # sales 和 ending_inv 已经是万元单位（ending_inv 已转换）
            sales_wan = total_sales / 10000
            ratio = (sales_wan / ending_inv) * 100
            return round(min(ratio, 999), 1)

        return None

    def _calc_dsi(self, turnover: Optional[float], report: Optional[Dict]) -> Optional[float]:
        """计算 DSI 库存天数"""
        # 优先从库存报表获取
        if report:
            td = self._safe_float(report.get("turnoverDays"))
            if td > 0:
                return round(td, 0)

        # 其次从周转率计算
        if turnover and turnover > 0:
            return round(365 / turnover, 0)

        return None

    def _calc_obsolete_ratio(self, movements: List[Dict], stock: List[Dict], report: Optional[Dict]) -> Optional[float]:
        """计算呆滞库存占比（%）"""
        # 优先从库存报表获取
        if report:
            slow_count = self._safe_float(report.get("slowMovingCount"))
            total_sku = self._safe_float(report.get("totalSkuCount"))
            if total_sku > 0 and slow_count >= 0:
                return round((slow_count / total_sku) * 100, 1)

        # 从 MSEG 最后移动日期分析 + MARD 有库存的物料
        if movements and stock:
            # 找出每个物料的最后移动日期
            last_move = {}
            for m in movements:
                matnr = m.get("matnr", "")
                budat = m.get("budat_mkpf") or m.get("budat", "")
                if matnr and budat:
                    if matnr not in last_move or budat > last_move[matnr]:
                        last_move[matnr] = budat

            # 统计有库存的物料中超过 180 天无移动的
            cutoff = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
            active_materials = set()
            for s in stock:
                matnr = s.get("matnr", "")
                labst = self._safe_float(s.get("labst"))
                if matnr and labst > 0:
                    active_materials.add(matnr)

            total_materials = len(active_materials)
            if total_materials == 0:
                return None

            obsolete_count = 0
            for matnr in active_materials:
                last_date = last_move.get(matnr, "")
                if not last_date or last_date < cutoff:
                    obsolete_count += 1

            return round((obsolete_count / total_materials) * 100, 1)

        return None

    def _calc_shortage_rate(self, reservations: List[Dict], stock: List[Dict]) -> Optional[float]:
        """
        计算缺料率（%）= 未满足预留数 / 总预留数
        注意：RESB 的 bdmng/enmng 是字符串格式
        """
        if not reservations:
            return None

        # 构建库存映射 matnr+werks -> available qty
        stock_map = {}
        for s in stock:
            key = f"{s.get('matnr', '')}_{s.get('werks', '')}"
            stock_map[key] = stock_map.get(key, 0) + self._safe_float(s.get("labst"))

        total_reservations = 0
        shortage_count = 0
        for r in reservations:
            bdmng = self._safe_float(r.get("bdmng"))  # 需求量
            enmng = self._safe_float(r.get("enmng"))  # 已领量
            remaining = bdmng - enmng
            if remaining <= 0:
                continue

            total_reservations += 1
            key = f"{r.get('matnr', '')}_{r.get('werks', '')}"
            available = stock_map.get(key, 0)
            if available < remaining:
                shortage_count += 1

        if total_reservations > 0:
            return round((shortage_count / total_reservations) * 100, 1)

        return None

    def _calc_forecast_accuracy(self, reservations: List[Dict], movements: List[Dict]) -> Optional[float]:
        """
        计算需求预测准确率（%）
        初期近似：用 预留需求量 vs 实际消耗量 的偏差
        注意：menge/bdmng 是字符串格式
        """
        if not reservations or not movements:
            return None

        # 按物料汇总预留需求量
        demand_by_mat = {}
        for r in reservations:
            matnr = r.get("matnr", "")
            bdmng = self._safe_float(r.get("bdmng"))
            if matnr and bdmng > 0:
                demand_by_mat[matnr] = demand_by_mat.get(matnr, 0) + bdmng

        # 按物料汇总实际消耗量
        consumption_types = {"261", "601"}
        actual_by_mat = {}
        for m in movements:
            matnr = m.get("matnr", "")
            bwart = str(m.get("bwart", ""))
            if matnr and bwart in consumption_types:
                menge = self._safe_float(m.get("menge"))
                if menge > 0:
                    actual_by_mat[matnr] = actual_by_mat.get(matnr, 0) + menge

        # 计算准确率
        common_materials = set(demand_by_mat.keys()) & set(actual_by_mat.keys())
        if not common_materials:
            return None

        total_accuracy = 0.0
        for matnr in common_materials:
            demand = demand_by_mat[matnr]
            actual = actual_by_mat[matnr]
            if demand > 0:
                accuracy = max(0, 1 - abs(demand - actual) / demand)
                total_accuracy += accuracy

        avg_accuracy = (total_accuracy / len(common_materials)) * 100
        return round(avg_accuracy, 1)

    def _build_metric(self, code: str, name: str, value: Optional[float]) -> Dict:
        """构建指标数据结构"""
        target_info = self.METRIC_TARGETS.get(code, {})
        target_value = target_info.get("target")
        unit = target_info.get("unit", "")
        direction = target_info.get("direction", "lower_is_better")

        # 如果真实值为 None，返回无数据状态
        if value is None:
            return {
                "id": code.lower(),
                "metric_code": code,
                "metric_name": name,
                "unit": unit,
                "current_value": None,
                "target_value": target_value,
                "severity": "info",
                "deviation": None,
                "data_source": "unavailable",
            }

        # 计算偏差和严重度
        if target_value is not None:
            if direction == "lower_is_better":
                deviation = round(value - target_value, 2)
                if deviation > target_value * 0.15:
                    severity = "critical"
                elif deviation > 0:
                    severity = "warning"
                else:
                    severity = "info"
            else:
                deviation = round(value - target_value, 2)
                if deviation < -target_value * 0.15:
                    severity = "critical"
                elif deviation < 0:
                    severity = "warning"
                else:
                    severity = "info"
        else:
            deviation = None
            severity = "info"

        return {
            "id": code.lower(),
            "metric_code": code,
            "metric_name": name,
            "unit": unit,
            "current_value": value,
            "target_value": target_value,
            "severity": severity,
            "deviation": deviation,
            "data_source": "erp",
        }

    # ========== 根因分析 ==========

    async def analyze_root_causes(self) -> List[Dict]:
        """
        基于真实数据分析库存成本偏高的根因
        
        Returns:
            根因列表（TOP3），每个根因包含影响金额、涉及物料、推荐操作
        """
        import asyncio

        # 获取数据
        (
            inventory_report,
            valuations,
            movements,
            stock_data,
        ) = await asyncio.gather(
            self.fetch_inventory_report(),
            self.fetch_inventory_valuation(),
            self.fetch_material_movements(days=180),
            self.fetch_inventory_stock(),
            return_exceptions=True,
        )

        # 容错处理
        if isinstance(inventory_report, Exception):
            inventory_report = None
        if isinstance(valuations, Exception):
            valuations = []
        if isinstance(movements, Exception):
            movements = []
        if isinstance(stock_data, Exception):
            stock_data = []

        root_causes = []

        # 根因1：呆滞库存分析
        obsolete_cause = self._analyze_obsolete_inventory(movements, stock_data, valuations, inventory_report)
        if obsolete_cause:
            root_causes.append(obsolete_cause)

        # 根因2：需求预测偏差
        forecast_cause = self._analyze_forecast_deviation(movements, stock_data, valuations)
        if forecast_cause:
            root_causes.append(forecast_cause)

        # 根因3：安全库存偏高
        safety_cause = self._analyze_safety_stock(stock_data, valuations)
        if safety_cause:
            root_causes.append(safety_cause)

        # 按影响金额排序
        root_causes.sort(key=lambda x: x.get("impact_value", 0), reverse=True)

        return root_causes[:3]

    def _analyze_obsolete_inventory(self, movements, stock, valuations, report) -> Optional[Dict]:
        """分析呆滞库存"""
        # 从报表获取
        if report and report.get("slowMovingCount"):
            slow_count = int(report.get("slowMovingCount", 0) or 0)
            total_sku = int(report.get("totalSkuCount", 0) or 0)
            total_value = float(report.get("totalValue", 0) or 0)
            if slow_count > 0 and total_sku > 0:
                ratio = (slow_count / total_sku) * 100
                # 估算呆滞金额
                obsolete_value = total_value * (ratio / 100)
                return {
                    "id": "rc_obsolete",
                    "title": "呆滞库存积压",
                    "description": f"超过180天未动的库存占比达 {ratio:.1f}%，金额约 {obsolete_value / 10000:.0f}万元",
                    "impact_level": "critical" if ratio > 15 else "warning",
                    "impact_value": round(obsolete_value / 10000, 0),
                    "impact_unit": "万元",
                    "related_materials": self._get_slow_moving_materials(movements, stock, valuations),
                    "recommended_actions": [
                        {
                            "id": "act_dispose",
                            "description": "生成呆滞物料处置方案（报废/折价/转移）",
                            "status": "pending",
                            "action_type": "generate_disposal_plan",
                        },
                        {
                            "id": "act_promo",
                            "description": "针对可用呆滞物料创建促销清仓计划",
                            "status": "pending",
                            "action_type": "create_clearance_plan",
                        },
                    ],
                }

        # 从移动数据分析
        if movements and stock:
            last_move = {}
            for m in movements:
                matnr = m.get("matnr", "")
                budat = m.get("budat_mkpf") or m.get("budat", "")
                if matnr and budat:
                    if matnr not in last_move or budat > last_move[matnr]:
                        last_move[matnr] = budat

            cutoff = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
            price_map = self._get_material_price_map(valuations)

            # 先按 matnr 去重（MARD 同物料可能有多仓位）
            active_materials = set()
            for s in stock:
                matnr = s.get("matnr", "")
                labst = self._safe_float(s.get("labst"))
                if matnr and labst > 0:
                    active_materials.add(matnr)

            # 汇总每个物料的总库存量
            stock_qty_map = {}
            for s in stock:
                matnr = s.get("matnr", "")
                labst = self._safe_float(s.get("labst"))
                if matnr and labst > 0:
                    stock_qty_map[matnr] = stock_qty_map.get(matnr, 0) + labst

            obsolete_set = {}  # matnr -> value（去重）
            for matnr in active_materials:
                last_date = last_move.get(matnr, "")
                if not last_date or last_date < cutoff:
                    price = price_map.get(matnr, 0)
                    qty = stock_qty_map.get(matnr, 0)
                    obsolete_set[matnr] = price * qty

            if obsolete_set:
                total_obsolete_value = sum(obsolete_set.values())
                total_stock = len(active_materials)
                ratio = (len(obsolete_set) / total_stock * 100) if total_stock > 0 else 0
                obsolete_materials = [
                    {"code": m, "name": m, "value": v}
                    for m, v in obsolete_set.items()
                ]

                return {
                    "id": "rc_obsolete",
                    "title": "呆滞库存积压",
                    "description": f"超过180天未动的库存占比达 {ratio:.1f}%，金额约 {total_obsolete_value / 10000:.0f}万元",
                    "impact_level": "critical" if ratio > 15 else "warning",
                    "impact_value": round(total_obsolete_value / 10000, 0),
                    "impact_unit": "万元",
                    "related_materials": [
                        {"code": m["code"], "name": m["name"]}
                        for m in sorted(obsolete_materials, key=lambda x: x["value"], reverse=True)[:6]
                    ],
                    "recommended_actions": [
                        {
                            "id": "act_dispose",
                            "description": "生成呆滞物料处置方案（报废/折价/转移）",
                            "status": "pending",
                            "action_type": "generate_disposal_plan",
                        },
                        {
                            "id": "act_promo",
                            "description": "针对可用呆滞物料创建促销清仓计划",
                            "status": "pending",
                            "action_type": "create_clearance_plan",
                        },
                    ],
                }

        return None

    def _analyze_forecast_deviation(self, movements, stock, valuations) -> Optional[Dict]:
        """分析需求预测偏差"""
        if not movements:
            return None

        # 按物料汇总实际消耗
        consumption_types = {"261", "601"}
        actual_by_mat = {}
        for m in movements:
            matnr = m.get("matnr", "")
            bwart = str(m.get("bwart", ""))
            if matnr and bwart in consumption_types:
                menge = self._safe_float(m.get("menge"))
                if menge > 0:
                    actual_by_mat[matnr] = actual_by_mat.get(matnr, 0) + menge

        # 使用 stprs * lbkum 估值
        price_map = self._get_material_price_map(valuations)
        lbkum_map = {v.get("matnr", ""): self._safe_float(v.get("lbkum"))
                     for v in valuations if v.get("matnr")}

        # 有库存但无消耗的物料视为预测偏差
        stock_materials = set(s.get("matnr", "") for s in stock
                             if s.get("matnr") and self._safe_float(s.get("labst")) > 0)
        consumed_materials = set(actual_by_mat.keys())
        over_stocked = stock_materials - consumed_materials

        if over_stocked:
            excess_value = sum(
                price_map.get(m, 0) * lbkum_map.get(m, 0)
                for m in over_stocked
            )
            if excess_value > 0:
                related = [
                    {"code": m, "name": m}
                    for m in sorted(over_stocked,
                                    key=lambda x: price_map.get(x, 0) * lbkum_map.get(x, 0),
                                    reverse=True)[:4]
                ]
                return {
                    "id": "rc_forecast",
                    "title": "需求预测偏差大",
                    "description": f"有库存但近期无消耗的物料 {len(over_stocked)} 项，涉及金额约 {excess_value / 10000:.0f}万元",
                    "impact_level": "warning",
                    "impact_value": round(excess_value / 10000, 0),
                    "impact_unit": "万元",
                    "related_materials": related,
                    "recommended_actions": [
                        {
                            "id": "act_forecast",
                            "description": "优化预测模型，引入ML算法提升准确率",
                            "status": "pending",
                            "action_type": "optimize_forecast",
                        },
                        {
                            "id": "act_review",
                            "description": "发起S&OP预测校准会议",
                            "status": "pending",
                            "action_type": "schedule_sop_review",
                        },
                    ],
                }

        return None

    def _analyze_safety_stock(self, stock, valuations) -> Optional[Dict]:
        """分析安全库存偏高"""
        if not stock or not valuations:
            return None

        price_map = self._get_material_price_map(valuations)

        # 按 matnr 汇总库存量（去重多仓位）
        stock_qty_map = {}
        for s in stock:
            matnr = s.get("matnr", "")
            labst = self._safe_float(s.get("labst"))
            if matnr and labst > 0:
                stock_qty_map[matnr] = stock_qty_map.get(matnr, 0) + labst

        high_stock = []
        for matnr, total_qty in stock_qty_map.items():
            price = price_map.get(matnr, 0)
            value = total_qty * price
            if value > 50000:  # 超过 5 万元的
                high_stock.append({"code": matnr, "name": matnr, "value": value})

        if high_stock:
            total_excess = sum(h["value"] for h in high_stock)
            # 假设可优化 30%
            optimizable = total_excess * 0.3
            return {
                "id": "rc_safety_stock",
                "title": "安全库存设置偏高",
                "description": f"{len(high_stock)}个物料库存金额较高，可优化释放资金约 {optimizable / 10000:.0f}万元",
                "impact_level": "warning",
                "impact_value": round(optimizable / 10000, 0),
                "impact_unit": "万元",
                "related_materials": [
                    {"code": h["code"], "name": h["name"]}
                    for h in sorted(high_stock, key=lambda x: x["value"], reverse=True)[:4]
                ],
                "recommended_actions": [
                    {
                        "id": "act_safety",
                        "description": "基于实际Lead Time重新计算安全库存水位",
                        "status": "pending",
                        "action_type": "recalculate_safety_stock",
                    }
                ],
            }

        return None

    def _get_slow_moving_materials(self, movements, stock, valuations) -> List[Dict]:
        """获取呆滞物料列表（按matnr去重）"""
        if not movements or not stock:
            return []

        last_move = {}
        for m in movements:
            matnr = m.get("matnr", "")
            budat = m.get("budat_mkpf") or m.get("budat", "")
            if matnr and budat:
                if matnr not in last_move or budat > last_move[matnr]:
                    last_move[matnr] = budat

        cutoff = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        price_map = self._get_material_price_map(valuations)

        # 按 matnr 汇总后去重
        stock_qty = {}
        for s in stock:
            matnr = s.get("matnr", "")
            labst = self._safe_float(s.get("labst"))
            if matnr and labst > 0:
                stock_qty[matnr] = stock_qty.get(matnr, 0) + labst

        slow = {}  # matnr -> value
        for matnr, qty in stock_qty.items():
            last_date = last_move.get(matnr, "")
            if not last_date or last_date < cutoff:
                price = price_map.get(matnr, 0)
                slow[matnr] = price * qty

        sorted_slow = sorted(slow.items(), key=lambda x: x[1], reverse=True)
        return [{"code": m, "name": m} for m, _ in sorted_slow[:6]]

    # ========== 快照与趋势 ==========

    def _save_snapshot(self, metrics: List[Dict]):
        """保存指标快照到 SQLite"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            cursor = self.db.conn.cursor()
            for m in metrics:
                if m.get("current_value") is not None:
                    cursor.execute('''
                        INSERT OR REPLACE INTO inventory_cost_metric_snapshot
                        (snapshot_date, metric_code, metric_value, target_value, unit)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (today, m["metric_code"], m["current_value"], m.get("target_value"), m.get("unit")))
            self.db.conn.commit()
        except Exception as e:
            logger.warning(f"保存指标快照失败: {e}")

    def get_trend_data(self, metric_code: str, days: int = 30) -> List[Dict]:
        """从快照表获取趋势数据"""
        try:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cursor = self.db.conn.cursor()
            cursor.execute('''
                SELECT snapshot_date, metric_value
                FROM inventory_cost_metric_snapshot
                WHERE metric_code = ? AND snapshot_date >= ?
                ORDER BY snapshot_date ASC
            ''', (metric_code, cutoff))
            rows = cursor.fetchall()
            return [{"date": row[0], "value": row[1]} for row in rows]
        except Exception as e:
            logger.warning(f"获取趋势数据失败: {e}")
            return []
