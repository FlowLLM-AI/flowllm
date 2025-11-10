# CompanyFactorOp 实现说明

## 概述
`CompanyFactorOp` 是一个用于构建公司整体估值金融因子逻辑图的操作类，它综合分析公司的多个业务板块，生成统一的因子传导路径图。

## 核心功能

### 输入参数
- `name`: 公司名称
- `code`: 股票代码

### 输出结果
返回一个包含以下字段的 JSON 对象：
```json
{
  "name": "公司名称",
  "code": "股票代码",
  "segments": ["板块1", "板块2", "板块3"],
  "meta_list": ["Meta信息1", "Meta信息2", ...],
  "factor_graph": "mermaid图代码"
}
```

## 执行流程

### Step 1: 获取业务板块
- 调用 `CompanyOperationOp` 获取公司的主营业务板块
- 过滤规则：
  - 营收或利润至少有一项 ≥ 5%
  - 按重要性排序（revenue + profit 降序）
  - 最多保留 3 个板块

### Step 2: 分析各业务板块
- 对每个保留的业务板块，串行调用 `CompanySegmentFactorOp`
- 每个板块返回：
  - `meta_list`: 该板块的Meta信息列表
  - `mermaid_graph`: 该板块的因子传导图

### Step 3: 合并Meta信息
- 收集所有板块的Meta信息
- 使用LLM进行智能合并：
  - 去除重复信息
  - 合并同义表述
  - 解决信息冲突
  - 按重要性排序

### Step 4: 融合因子逻辑图
- 收集所有板块的因子传导图
- 使用LLM进行图融合：
  - 统一收敛点：`A[公司名 估值增加]`
  - 提取和合并相同/相似因子
  - 优化传导路径（最多5条，每条≤4个节点）
  - 确保所有因子有Meta信息支撑

### Step 5: 验证并修正Mermaid代码
- 检查语法正确性
- 验证结构规范性
- 修复常见错误
- 确保可正常渲染

### Step 6: 输出最终结果
- 构建包含所有信息的结果字典
- 以JSON格式输出

## CompanySegmentFactorOp 的改进

为了支持 `CompanyFactorOp`，对 `CompanySegmentFactorOp` 进行了改进：

### 返回值变更
- **修改前**：只返回 `mermaid_graph` 字符串
- **修改后**：返回包含 `meta_list` 和 `mermaid_graph` 的JSON对象

### 主要改动
1. **初始化变更**：`meta_list` 从字符串改为空列表 `[]`
2. **类型调整**：所有内部方法的 `meta_list` 参数类型从 `str` 改为 `List`
3. **JSON序列化**：在prompt中使用时，通过 `json.dumps()` 将列表转为字符串
4. **返回格式**：最终返回包含两个字段的字典，并序列化为JSON字符串

### 向后兼容性
- 这个改动会影响现有的使用 `CompanySegmentFactorOp` 的代码
- 如需继续单独使用该Op且只获取mermaid图，可通过 `json.loads(op.output)["mermaid_graph"]` 提取

## 提示词设计

### 复用的提示词（来自CompanySegmentFactorOp）
- `init_mermaid_graph`: 初始化mermaid图
- `factor_step1_prompt`: 生成搜索查询
- `factor_step2_prompt`: 更新Meta信息列表
- `factor_step3_prompt`: 更新因子传导图

### 新增的提示词

#### merge_meta_prompt
- 功能：合并多个板块的Meta信息
- 要求：去重、同义合并、冲突解决、按重要性排序

#### merge_graphs_prompt
- 功能：融合多个板块的因子传导图
- 要求：
  - 统一收敛点
  - 因子去重和归类
  - 路径优化（最多5条，每条≤4节点）
  - 依据约束（所有因子必须有Meta支撑）

#### validate_mermaid_prompt
- 功能：验证并修正Mermaid代码
- 检查项：
  - 语法正确性（graph LR; 开头，箭头格式等）
  - 结构规范性（收敛点、无循环、无孤立节点）
  - 节点命名规范
  - 常见错误修复

## 配置参数

### CompanyFactorOp 参数
- `llm`: LLM模型（默认 "qwen3_30b_instruct"）
- `revenue_threshold`: 营收阈值（默认 0.05，即5%）
- `profit_threshold`: 利润阈值（默认 0.05，即5%）
- `max_segments`: 最多保留的板块数（默认 3）

### CompanySegmentFactorOp 参数
- `llm`: LLM模型（默认 "qwen3_30b_instruct"）
- `max_steps`: 最大迭代步数（默认 3）
- `max_search_cnt`: 每次最多搜索查询数（默认 3）
- `max_approach_cnt`: 最多传导路径数（默认 3）

## 使用示例

```python
from flowllm.app import FlowLLMApp
from flowllm.op.fin_search.company_factor_op import CompanyFactorOp

async with FlowLLMApp(args=["config=fin_research"]):
    op = CompanyFactorOp()
    await op.async_call(name="阿里巴巴", code="09988")
    print(op.output)
```

## 输出示例

```json
{
  "name": "阿里巴巴",
  "code": "09988",
  "segments": ["云计算", "电商", "AI"],
  "meta_list": [
    "政府推出AI产业扶持政策",
    "云计算市场需求增长30%",
    "电商平台GMV同比增长15%",
    "阿里云Q3营收增长28%"
  ],
  "factor_graph": "graph LR;\nAI需求增 --> 云服务收入增\n政策支持 --> 云服务收入增\n云服务收入增 --> A[阿里巴巴 估值增加]\n电商增长 --> A[阿里巴巴 估值增加]"
}
```

## 技术亮点

1. **模块化设计**：通过组合现有Op（CompanyOperationOp、CompanySegmentFactorOpV2）实现复杂功能
2. **智能过滤**：基于营收和利润指标自动筛选核心业务板块
3. **LLM驱动**：利用LLM的理解能力进行Meta信息合并和因子图融合
4. **串行处理**：确保每个板块分析完整且可追溯
5. **自动验证**：内置Mermaid代码验证和修正机制
6. **结构化输出**：统一的JSON格式便于后续处理

## 注意事项

1. **执行时间**：由于需要串行处理多个板块，整体执行时间较长
2. **依赖关系**：需要确保 `CompanyOperationOp` 和 `TongyiMcpSearchOp` 正常工作
3. **网络搜索**：依赖外部搜索服务，可能受网络状况影响
4. **LLM质量**：最终结果质量依赖于LLM的推理能力
5. **配置调优**：可根据实际需求调整阈值和最大数量参数

