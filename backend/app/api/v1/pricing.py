"""
核价相关API端点
"""
import logging
import time
import random
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
import pandas as pd
import io

from ...schemas.pricing import (
    MaterialData, PricingResult, BatchPricingRequest, BatchPricingResponse,
    PricingStatistics, ExcelUploadResponse, PricingSaveRequest, PricingSaveResponse,
    ComplexityLevel, PricingStatus
)
from ...repository.pricing_repo import PricingRepository

logger = logging.getLogger(__name__)

router = APIRouter()

# 依赖注入
def get_pricing_repository() -> PricingRepository:
    return PricingRepository()


@router.post("/pricing/parse-excel", response_model=ExcelUploadResponse)
async def parse_excel_file(
    file: UploadFile = File(...),
    repo: PricingRepository = Depends(get_pricing_repository)
):
    """解析Excel文件，提取物料数据"""
    try:
        # 检查文件类型
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="只支持Excel文件格式")
        
        # 读取文件内容
        contents = await file.read()
        
        # 使用pandas解析Excel
        try:
            df = pd.read_excel(io.BytesIO(contents))
        except Exception as e:
            logger.error(f"Excel解析失败: {e}")
            raise HTTPException(status_code=400, detail=f"Excel文件解析失败: {str(e)}")
        
        # 验证必要的列
        required_columns = ['物料编码', '物料名称', '规格型号', '数量', '单位', '复杂度']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400, 
                detail=f"Excel文件缺少必要列: {', '.join(missing_columns)}"
            )
        
        # 转换为MaterialData对象
        materials = []
        error_rows = []
        
        for index, row in df.iterrows():
            try:
                # 处理工艺要求列（可能不存在）
                process_requirements = []
                if '工艺要求' in df.columns:
                    process_str = str(row.get('工艺要求', ''))
                    if process_str and process_str != 'nan':
                        process_requirements = [req.strip() for req in process_str.split(',')]
                
                # 验证复杂度等级
                complexity_str = str(row.get('复杂度', '中等')).strip()
                if complexity_str not in ['简单', '中等', '复杂']:
                    complexity_str = '中等'
                
                material = MaterialData(
                    material_code=str(row['物料编码']).strip(),
                    material_name=str(row['物料名称']).strip(),
                    specification=str(row['规格型号']).strip(),
                    quantity=int(row['数量']),
                    unit=str(row['单位']).strip(),
                    complexity=ComplexityLevel(complexity_str),
                    process_requirements=process_requirements
                )
                materials.append(material)
                
            except Exception as e:
                logger.warning(f"第{index+1}行数据解析失败: {e}")
                error_rows.append(index + 1)
        
        return ExcelUploadResponse(
            success=True,
            message=f"成功解析 {len(materials)} 条物料数据",
            data=materials,
            error_rows=error_rows if error_rows else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excel文件处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")


@router.post("/pricing/batch-calculate", response_model=BatchPricingResponse)
async def batch_calculate_pricing(
    request: BatchPricingRequest,
    repo: PricingRepository = Depends(get_pricing_repository)
):
    """批量核价计算"""
    start_time = time.time()
    
    try:
        results = []
        
        for material in request.materials:
            # 模拟核价计算逻辑
            result = await calculate_pricing_for_material(material)
            results.append(result)
        
        # 保存核价结果到数据库
        saved_results = await repo.batch_create_pricing_results(results)
        
        processing_time = time.time() - start_time
        
        return BatchPricingResponse(
            success=True,
            message=f"成功完成 {len(results)} 项核价分析",
            data=saved_results,
            total_count=len(results),
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"批量核价计算失败: {e}")
        raise HTTPException(status_code=500, detail=f"核价计算失败: {str(e)}")


async def calculate_pricing_for_material(material: MaterialData) -> PricingResult:
    """为单个物料计算核价"""
    try:
        # 根据复杂度计算基础成本
        base_costs = {
            ComplexityLevel.SIMPLE: 800,
            ComplexityLevel.MEDIUM: 1500,
            ComplexityLevel.COMPLEX: 2500
        }
        base_cost = base_costs.get(material.complexity, 1200)
        
        # 内部制造成本（包含人工、设备、材料等）
        # 添加一些随机因素模拟真实情况
        internal_cost = base_cost + random.randint(0, 400)
        
        # 外协加工成本（通常比内部成本略低，但有波动）
        external_cost = base_cost + random.randint(-200, 400)
        
        cost_difference = external_cost - internal_cost
        
        # 生成智能建议
        recommendation = generate_pricing_recommendation(cost_difference, material)
        
        return PricingResult(
            material_code=material.material_code,
            material_name=material.material_name,
            specification=material.specification,
            quantity=material.quantity,
            unit=material.unit,
            internal_cost=internal_cost,
            external_cost=external_cost,
            cost_difference=cost_difference,
            recommendation=recommendation,
            status=PricingStatus.PENDING
        )
        
    except Exception as e:
        logger.error(f"物料 {material.material_code} 核价计算失败: {e}")
        raise


def generate_pricing_recommendation(cost_difference: float, material: MaterialData) -> str:
    """生成核价建议"""
    if cost_difference < -200:
        return f"✅ 强烈建议外协，节省成本{abs(cost_difference):.0f}元/件，预计总节省{cost_difference * material.quantity:.0f}元"
    elif cost_difference < -50:
        return f"✅ 建议外协，节省成本{abs(cost_difference):.0f}元/件，预计总节省{cost_difference * material.quantity:.0f}元"
    elif cost_difference < 50:
        return "⚠️ 成本相近，建议评估供应商质量、交期和服务能力后决定"
    elif cost_difference < 200:
        return f"⚠️ 外协成本略高{cost_difference:.0f}元/件，建议评估内部产能和成本优化空间"
    else:
        return f"❌ 不建议外协，成本增加{cost_difference:.0f}元/件，建议内部生产"


@router.get("/pricing/statistics", response_model=PricingStatistics)
async def get_pricing_statistics(
    repo: PricingRepository = Depends(get_pricing_repository)
):
    """获取核价统计信息"""
    try:
        statistics = await repo.get_pricing_statistics()
        return statistics
    except Exception as e:
        logger.error(f"获取核价统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.post("/pricing/save-results", response_model=PricingSaveResponse)
async def save_pricing_results(
    request: PricingSaveRequest,
    repo: PricingRepository = Depends(get_pricing_repository)
):
    """保存核价结果"""
    try:
        # 只保存已确认的结果
        approved_results = [r for r in request.results if r.status == PricingStatus.APPROVED or r.status == "approved"]
        
        if not approved_results:
            return PricingSaveResponse(
                success=False,
                message="没有已确认的核价结果需要保存",
                saved_count=0
            )
        
        # 更新结果状态（如果还未保存）
        for result in approved_results:
            await repo.update_pricing_result_status(
                result.id, 
                PricingStatus.APPROVED, 
                "系统保存"
            )
        
        # 保存到历史记录
        batch_id = f"batch_{int(time.time())}"
        for result in approved_results:
            history = PricingHistory(
                batch_id=batch_id,
                material_code=result.material_code,
                material_name=result.material_name,
                internal_cost=result.internal_cost,
                external_cost=result.external_cost,
                final_decision="approved" if result.status == PricingStatus.APPROVED else "pending",
                decision_reason=result.recommendation
            )
            await repo.save_pricing_history(history)
        
        return PricingSaveResponse(
            success=True,
            message=f"成功保存 {len(approved_results)} 条核价记录",
            saved_count=len(approved_results),
            batch_id=batch_id
        )
        
    except Exception as e:
        logger.error(f"保存核价结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.put("/pricing/results/{result_id}/approve")
async def approve_pricing_result(
    result_id: str,
    approved_by: str = "当前用户",
    repo: PricingRepository = Depends(get_pricing_repository)
):
    """确认单个核价结果"""
    try:
        success = await repo.update_pricing_result_status(
            result_id, 
            PricingStatus.APPROVED, 
            approved_by
        )
        
        if success:
            return {"success": True, "message": "确认成功"}
        else:
            raise HTTPException(status_code=404, detail="核价结果不存在")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"确认核价结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"确认失败: {str(e)}")


@router.put("/pricing/results/batch-approve")
async def batch_approve_pricing_results(
    result_ids: List[str],
    approved_by: str = "当前用户",
    repo: PricingRepository = Depends(get_pricing_repository)
):
    """批量确认核价结果"""
    try:
        updated_count = await repo.batch_update_pricing_status(
            result_ids, 
            PricingStatus.APPROVED, 
            approved_by
        )
        
        return {
            "success": True, 
            "message": f"批量确认成功，共确认 {updated_count} 个项目",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"批量确认核价结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量确认失败: {str(e)}")


@router.get("/pricing/results", response_model=List[PricingResult])
async def get_pricing_results(
    skip: int = 0,
    limit: int = 100,
    status: str = None,
    repo: PricingRepository = Depends(get_pricing_repository)
):
    """获取核价结果列表"""
    try:
        pricing_status = None
        if status and status in ["pending", "approved", "rejected"]:
            pricing_status = PricingStatus(status)
        
        results = await repo.get_pricing_results(skip, limit, pricing_status)
        return results
        
    except Exception as e:
        logger.error(f"获取核价结果列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取结果失败: {str(e)}")


@router.get("/pricing/materials", response_model=List[MaterialData])
async def get_materials(
    skip: int = 0,
    limit: int = 100,
    repo: PricingRepository = Depends(get_pricing_repository)
):
    """获取物料列表"""
    try:
        materials = await repo.get_materials(skip, limit)
        return materials
        
    except Exception as e:
        logger.error(f"获取物料列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取物料失败: {str(e)}")


@router.post("/pricing/demo-data")
async def create_demo_data(
    repo: PricingRepository = Depends(get_pricing_repository)
):
    """创建演示数据"""
    try:
        # 邵阳纺机示例物料数据
        demo_materials = [
            MaterialData(
                material_code="SY001",
                material_name="纺机主轴",
                specification="Φ50×200mm",
                quantity=100,
                unit="件",
                complexity=ComplexityLevel.MEDIUM,
                process_requirements=["车削", "磨削", "热处理"]
            ),
            MaterialData(
                material_code="SY002",
                material_name="纺机齿轮",
                specification="模数2.5",
                quantity=50,
                unit="件",
                complexity=ComplexityLevel.COMPLEX,
                process_requirements=["铣削", "滚齿", "淬火"]
            ),
            MaterialData(
                material_code="SY003",
                material_name="纺机轴承座",
                specification="内径30mm",
                quantity=200,
                unit="件",
                complexity=ComplexityLevel.SIMPLE,
                process_requirements=["车削", "钻孔"]
            ),
            MaterialData(
                material_code="SY004",
                material_name="纺机联轴器",
                specification="弹性联轴器",
                quantity=80,
                unit="件",
                complexity=ComplexityLevel.MEDIUM,
                process_requirements=["车削", "铣削", "装配"]
            ),
            MaterialData(
                material_code="SY005",
                material_name="纺机皮带轮",
                specification="Φ150mm",
                quantity=120,
                unit="件",
                complexity=ComplexityLevel.SIMPLE,
                process_requirements=["车削", "滚齿"]
            )
        ]
        
        # 创建物料数据
        created_materials = []
        for material in demo_materials:
            created_material = await repo.create_material(material)
            created_materials.append(created_material)
        
        return {
            "success": True,
            "message": f"成功创建 {len(created_materials)} 条演示物料数据",
            "data": created_materials
        }
        
    except Exception as e:
        logger.error(f"创建演示数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建演示数据失败: {str(e)}")


# 导入PricingHistory（需要添加到schemas中）
from ...schemas.pricing import PricingHistory
