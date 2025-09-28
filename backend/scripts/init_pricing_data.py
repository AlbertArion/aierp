#!/usr/bin/env python3
"""
初始化邵阳纺机核价示例数据
"""
import sys
import os
import asyncio
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.pricing import MaterialData, PricingResult, ComplexityLevel, PricingStatus
from app.repository.pricing_repo import PricingRepository
from app.db.mongo import get_db


async def init_pricing_data():
    """初始化核价相关数据"""
    print("🚀 开始初始化邵阳纺机核价示例数据...")
    
    # 初始化数据库
    db = get_db()
    
    # 如果是SQLite数据库，需要先创建表
    if hasattr(db, 'conn'):
        print("🗄️ 初始化SQLite表结构...")
        cursor = db.conn.cursor()
        
        # 创建materials表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS materials (
                id TEXT PRIMARY KEY,
                material_code TEXT NOT NULL,
                material_name TEXT NOT NULL,
                specification TEXT,
                quantity INTEGER,
                unit TEXT,
                complexity TEXT,
                process_requirements TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        # 创建pricing_results表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pricing_results (
                id TEXT PRIMARY KEY,
                material_code TEXT NOT NULL,
                material_name TEXT NOT NULL,
                specification TEXT,
                quantity INTEGER,
                unit TEXT,
                internal_cost REAL,
                external_cost REAL,
                cost_difference REAL,
                recommendation TEXT,
                status TEXT,
                approval_time TEXT,
                approved_by TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        # 创建pricing_rules表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pricing_rules (
                id TEXT PRIMARY KEY,
                rule_name TEXT NOT NULL,
                rule_type TEXT,
                conditions TEXT,
                actions TEXT,
                priority INTEGER,
                is_active BOOLEAN,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        # 创建pricing_history表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pricing_history (
                id TEXT PRIMARY KEY,
                batch_id TEXT,
                material_code TEXT,
                material_name TEXT,
                internal_cost REAL,
                external_cost REAL,
                final_decision TEXT,
                decision_reason TEXT,
                created_at TEXT
            )
        ''')
        
        db.conn.commit()
        print("✅ SQLite表结构创建完成")
    
    pricing_repo = PricingRepository()
    
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
        ),
        MaterialData(
            material_code="SY006",
            material_name="纺机导纱器",
            specification="不锈钢材质",
            quantity=150,
            unit="件",
            complexity=ComplexityLevel.MEDIUM,
            process_requirements=["冲压", "抛光", "装配"]
        ),
        MaterialData(
            material_code="SY007",
            material_name="纺机张力器",
            specification="弹簧式",
            quantity=90,
            unit="件",
            complexity=ComplexityLevel.COMPLEX,
            process_requirements=["车削", "热处理", "装配", "调试"]
        ),
        MaterialData(
            material_code="SY008",
            material_name="纺机罗拉",
            specification="Φ80×300mm",
            quantity=60,
            unit="件",
            complexity=ComplexityLevel.COMPLEX,
            process_requirements=["车削", "磨削", "表面处理"]
        ),
        MaterialData(
            material_code="SY009",
            material_name="纺机锭子",
            specification="高速锭子",
            quantity=300,
            unit="件",
            complexity=ComplexityLevel.MEDIUM,
            process_requirements=["车削", "热处理", "动平衡"]
        ),
        MaterialData(
            material_code="SY010",
            material_name="纺机钢领",
            specification="环锭纺",
            quantity=180,
            unit="件",
            complexity=ComplexityLevel.MEDIUM,
            process_requirements=["冲压", "热处理", "精加工"]
        )
    ]
    
    # 创建物料数据
    print("📦 创建物料数据...")
    created_materials = []
    for material in demo_materials:
        try:
            created_material = await pricing_repo.create_material(material)
            created_materials.append(created_material)
            print(f"  ✅ 创建物料: {material.material_code} - {material.material_name}")
        except Exception as e:
            print(f"  ❌ 创建物料失败: {material.material_code} - {e}")
    
    print(f"📊 成功创建 {len(created_materials)} 条物料数据")
    
    # 生成示例核价结果
    print("💰 生成示例核价结果...")
    import random
    
    demo_pricing_results = []
    for material in created_materials:
        # 根据复杂度计算基础成本
        base_costs = {
            ComplexityLevel.SIMPLE: 800,
            ComplexityLevel.MEDIUM: 1500,
            ComplexityLevel.COMPLEX: 2500
        }
        base_cost = base_costs.get(material.complexity, 1200)
        
        # 内部制造成本（包含人工、设备、材料等）
        internal_cost = base_cost + random.randint(0, 400)
        
        # 外协加工成本（通常比内部成本略低，但有波动）
        external_cost = base_cost + random.randint(-200, 400)
        
        cost_difference = external_cost - internal_cost
        
        # 生成智能建议
        if cost_difference < -100:
            recommendation = f"✅ 强烈建议外协，节省成本{abs(cost_difference):.0f}元/件"
        elif cost_difference < -50:
            recommendation = f"✅ 建议外协，节省成本{abs(cost_difference):.0f}元/件"
        elif cost_difference < 50:
            recommendation = "⚠️ 成本相近，建议评估质量和服务"
        elif cost_difference < 200:
            recommendation = f"⚠️ 外协成本略高{cost_difference:.0f}元/件，建议评估内部产能"
        else:
            recommendation = f"❌ 不建议外协，成本增加{cost_difference:.0f}元/件"
        
        pricing_result = PricingResult(
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
        demo_pricing_results.append(pricing_result)
    
    # 保存核价结果
    try:
        saved_results = await pricing_repo.batch_create_pricing_results(demo_pricing_results)
        print(f"  ✅ 成功生成 {len(saved_results)} 条核价结果")
    except Exception as e:
        print(f"  ❌ 生成核价结果失败: {e}")
    
    print("🎉 邵阳纺机核价示例数据初始化完成！")
    print(f"📈 数据统计:")
    print(f"  - 物料数据: {len(created_materials)} 条")
    print(f"  - 核价结果: {len(demo_pricing_results)} 条")
    
    return {
        "materials_count": len(created_materials),
        "pricing_results_count": len(demo_pricing_results)
    }


if __name__ == "__main__":
    asyncio.run(init_pricing_data())
