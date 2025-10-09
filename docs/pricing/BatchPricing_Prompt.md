## 批量核价智能体需求提示词（Prompt）

本提示词用于指导“核价智能体”在自研ERP核价系统中完成“批量核价”能力构建与执行。目标是让数字员工接收一批物料数据，自动进行核价计算、产出批量结果，并支持领导确认与结果入库，全流程可追溯、可复现。

### 1. 背景与目标
- **现状**：已有“单物料核价”功能与接口（参考前端 `PricingAgent.vue` 及后端 `/api/pricing/ai-query` 逻辑）。
- **诉求**：支持“批量核价”。用户通过导入一批物料数据（如 `docs/pricing/核算单*.xlsx`），由智能体自动核价，形成批量结果清单，支持领导确认后保存。
- **角色定位**：数字员工（批量核价专员）：接单→解析→校验→计算→汇总→请示→归档。

### 2. 输入与数据来源
- **批量输入文件**：Excel（XLSX）。示例：`docs/pricing/核算单2025-09-25 23_04_57.xlsx`。
  - 典型字段（需容错与映射）：
    - 物料编码（material_code）
    - 物料名称（material_name）
    - 规格型号（specification）
    - 工艺/要求（process_requirements）
    - 数量/计量单位（quantity / uom）
    - 其他可选：客户/项目、期望交期、价格参考来源等
- **核价规则依据**：`docs/pricing/FS-COM-核算标准价_-V1.3-250605.docx`（作为规则文档参考），以及系统内置工艺/成本/参数表（如存在）。
- **系统基准数据**：已有数据库（物料库、工艺要求、历史价格、BOM/工序、人工/设备/能耗等）。

### 3. 输出与交付物
- **批量核价结果表**（建议字段）：
  - material_code, material_name, specification, process_requirements
  - estimated_price（核算价/建议价）
  - currency（货币）
  - status（success/failed/pending_review）
  - reason_or_notes（失败原因/说明/计算摘要）
  - rule_version（规则版本/参数快照标识）
  - calc_trace_id（本次批量任务ID，便于追溯）
- **导出**：支持 CSV/XLSX 导出给领导确认。
- **入库**：领导确认后批量写入数据库（带版本与审计信息）。

### 4. 关键流程（期望智能体执行步骤）
1) 接收文件与任务创建
   - 解析Excel：首行标题识别、列名标准化（中英/大小写/别名映射）。
   - 生成 `calc_trace_id` 与任务元数据（来源、人、时间、文件名、行数）。
2) 数据清洗与校验
   - 行级去重（material_code+specification+process_requirements）。
   - 必填项校验（编码/名称至少其一；规格/工艺建议必填）。
   - 参考库校验：物料是否存在、已知规格/工艺是否合法。
   - 缺失/异常生成“待补充清单”。
3) 参数补齐与策略选择
   - 根据规则文档与历史数据，推断缺省参数（如工序、损耗率、人工/设备单价）。
   - 若存在多策略（标准价/快速估价/历史均价/相似物料推断），给出选择与理由。
4) 逐行核价计算
   - 依据统一核价函数/服务进行计算，返回 `estimated_price` 与过程摘要。
   - 对异常行标注 `status=failed` 并记录 `reason_or_notes`。
5) 汇总与复核
   - 汇总统计：成功条数、失败条数、均价、区间、异常TopN。
   - 生成“领导确认版”预览（可分页/筛选/导出）。
6) 领导确认与保存
   - 支持“全部通过/部分通过/驳回重算”。
   - 通过后批量入库，记录 `rule_version` 与 `calc_trace_id`，写审计日志。
7) 归档与通知
   - 生成结果快照（CSV/XLSX + 元数据JSON）。
   - 可选：通知相关人（站内信/邮件/IM Webhook）。

### 5. 约束与质量要求
- 严禁“编造数据”。无法核价时，必须 `status=failed` 并写明原因。
- 可复现：保留输入快照、规则/参数版本、计算摘要，保证复核可重放。
- 时间与性能：支持至少 1,000 行/批（可分批提交与并发），给出进度反馈。
- 容错与可解释：对模糊匹配/相似推荐需给出解释与置信度。

### 6. 接口与前后端对接（建议）
- 上传接口：`POST /api/pricing/batch/upload`
  - form-data: `file`(xlsx), `task_name`(optional)
  - resp: `{ trace_id, total_rows, normalized_columns, preview_rows }`
- 预检与解析：`GET /api/pricing/batch/{trace_id}/preview`
- 执行核价：`POST /api/pricing/batch/{trace_id}/run`
  - body 可选参数：策略选项、并发度、是否使用历史参考等
  - resp: `{ success, stats: {success_count, failed_count}, sample }`
- 查看结果：`GET /api/pricing/batch/{trace_id}/results?status=all|success|failed&pn=1&ps=50`
- 导出结果：`GET /api/pricing/batch/{trace_id}/export?format=xlsx|csv`
- 领导确认：`POST /api/pricing/batch/{trace_id}/approve`
  - body: `{ approve: true|false, partial_ids?: string[], comment?: string }`
- 入库保存：由后端在 `approve=true` 时触发（带 `rule_version` 与审计日志）。

说明：保留与现有 `/api/pricing/ai-query` 的兼容，用于单条/自然语言核价问答；批量核价以独立任务接口管理。

### 7. 字段映射与容错（示例）
- 列名映射（示例，不限于）：
  - 物料编码 → material_code / 编码 / 料号 / 物料号
  - 物料名称 → material_name / 名称 / 品名
  - 规格型号 → specification / 规格 / 型号 / 规格型号
  - 工艺/要求 → process_requirements / 工艺 / 要求 / 工艺要求
  - 数量 → quantity / 数量 / QTY
- 值域与格式：
  - 去除前后空白、全角半角统一、大小写统一、特殊符号标准化。
  - 空值策略：若关键字段缺失，标记失败并输出补充建议。

### 8. 规则与计算（结合文档与现状）
- 参考 `FS-COM-核算标准价_-V1.3-250605.docx` 归纳关键参数：
  - 材料成本（主材/辅材/损耗）
  - 加工成本（工序工时×单价）
  - 制造费用/管理费用分摊
  - 税率、利润率策略
- 结合现有“单物料核价”逻辑：
  - 统一核价服务：`estimate_price(material)` 返回 `estimated_price` 与摘要
  - 支持历史价格/相似物料参考（如可用）
  - 失败路径必须返回原因

### 9. 审计与追溯
- 保存：输入文件快照、规范化后的列、规则/参数版本、计算摘要、操作者、时间。
- 结果可追溯到单行输入与计算过程（trace_id + row_id）。

### 10. 安全与权限
- 上传与执行需具备相应角色（如采购/成本工程师/价格管理员）。
- 批量结果仅对任务创建人、相关项目成员与领导可见。

### 11. 人机交互（前端建议）
- 前端入口：在 `PricingAgent.vue` 增加“批量核价”页签或入口。
- 流程UI：上传→预检→参数选择→执行→进度条→结果表→筛选→导出→提交领导。
- 移动端适配：结果表横向滚动、分屏查看摘要与明细。
- 统一风格：沿用现有“核价智能体”聊天风格，增加任务状态流（Steps/Result）。

### 12. 示例对话（Few-shot）
- 用户：我有一份物料清单，帮我批量核价。
- 智能体：请上传Excel文件。支持的列包括物料编码/名称/规格/工艺… 我会先做预检并给出异常项清单。
- 用户：（上传excel）
- 智能体：已解析共 532 行，去重后 518 行；发现 12 行缺少规格，8 行工艺不规范。是否按“标准价策略”执行计算？
- 用户：按标准价，开始。
- 智能体：正在计算…（进度 35%）…（进度 100%）。成功 490 行，失败 28 行。是否导出结果并提交领导确认？
- 用户：导出并提交。
- 智能体：已导出xlsx并发起领导确认，追踪ID：`BP-20250930-0007`。

---

请严格遵守：
- 不臆造数据；无法核价要说明原因。
- 记录可复现的参数与版本。
- 结果呈现优先“清晰可读、可导出、可筛选”。


