## 背景

### 系统架构

采用分层架构设计：

1. **操作层（Operation Layer）**：提供原子化的数据操作能力，每个Op（操作）负责特定的数据获取或处理任务
2. **流程层（Flow Layer）**：通过Pipeline将多个Op组合成复杂的业务流程，支持串行（>>）和并行（|）执行和子Op（<<）
3. **服务层（Service Layer）**：基于MCP（Model Context Protocol）协议提供标准化的API接口

### 核心特性

- **模块化设计**：每个供给模块独立可配置，支持按需组合和扩展
- **统一接口**：基于MCP协议提供标准化的工具调用接口，便于集成
- **智能缓存**：支持多级缓存机制，提高数据获取效率和降低成本
- **灵活配置**：通过YAML配置文件管理流程参数，支持环境隔离和版本管理

### 供给模块

系统目前提供以下金融供给模块，共计28个Flow：

| MCP Flow名称                | 核心能力               |
|---------------------------|--------------------|
| **ant_search**            | 内部专业搜索             |
| **ant_investment**        | 投资分析服务             |
| **extract_entities_code** | 金融实体识别和code提取      |
| **akshare_market**        | A股实时行情数据           |
| **akshare_calculate**     | 股票技术分析计算           |
| **qtf_brief_mcp**         | 股票基础分析摘要           |
| **qtf_medium_mcp**        | 股票中等深度分析           |
| **qtf_full_mcp**          | 股票全面深度分析           |
| **tavily_search**         | tavily_search      |
| **dashscope_search**      | dashscope大模型强制开启搜索 |
| **bailian_web_search**    | bailian_search     |
| **bocha_web_search**      | bocha search       |
| **brave_web_search**      | brave search       |
| **bailian_web_parser**    | bailian 网页解析       |
| **crawl_ths_company**     | 同花顺公司基本资料          |
| **crawl_ths_holder**      | 同花顺股东研究信息          |
| **crawl_ths_operate**     | 同花顺经营分析信息          |
| **crawl_ths_equity**      | 同花顺股本结构信息          |
| **crawl_ths_capital**     | 同花顺资本运作信息          |
| **crawl_ths_worth**       | 同花顺盈利预测信息          |
| **crawl_ths_news**        | 同花顺新闻公告信息          |
| **crawl_ths_concept**     | 同花顺概念题材信息          |
| **crawl_ths_position**    | 同花顺主力持仓信息          |
| **crawl_ths_finance**     | 同花顺财务分析信息          |
| **crawl_ths_bonus**       | 同花顺分红融资信息          |
| **crawl_ths_event**       | 同花顺公司大事信息          |
| **crawl_ths_field**       | 同花顺行业对比信息          |

### 供给类型统计

| 分类         | 供给名称                           | 输入示例                                                       | 输出示例                                                                                                                                                                                     |
|------------|--------------------------------|------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **专业供给**   | ant_search（专业搜索）               | `{"query": "平安银行最新财报分析"}`                                  | `平安银行2024年Q3财报显示：...`                                                                                                                                                                    |
|            | ant_investment（投资分析）           | `{"entity": "阿里巴巴", "analysis_category": "股票"}`            | `阿里巴巴投资分析：...`                                                                                                                                                                           |
| **通用搜索解析** | tavily_search（Tavily搜索）        | `{"query": "2024年中国GDP增长情况"}`                              | `根据最新数据，2024年中国GDP同比增长5.2%，经济运行总体平稳，消费和投资成为主要增长动力...`                                                                                                                                    |
|            | dashscope_search（通义搜索）         | `{"query": "人工智能最新发展趋势"}`                                  | `人工智能领域最新发展包括大语言模型技术突破、多模态AI应用普及、AI+行业深度融合等趋势...`                                                                                                                                        |
|            | bailian_web_search（百炼搜索）       | `{"query": "新能源汽车市场现状", "count": 10}`                      | `2024年新能源汽车市场保持高速增长，销量突破800万辆，市场渗透率达到35%，比亚迪、特斯拉领跑市场...`                                                                                                                                 |
|            | bocha_web_search（Bocha搜索）      | `{"query": "区块链技术应用", "freshness": 7}`                     | `区块链技术在金融、供应链、数字身份等领域应用不断深化，央行数字货币DCEP试点扩大，DeFi生态持续发展...`                                                                                                                                |
|            | brave_web_search（Brave搜索）      | `{"query": "量子计算突破", "count": 5}`                          | `量子计算领域取得重大突破，IBM发布1000+量子比特处理器，Google实现量子纠错里程碑，产业化进程加速...`                                                                                                                              |
|            | bailian_web_parser（网页解析）       | `{"url": "https://example.com"}`                           | `解析网页内容：标题、正文、关键信息等结构化数据，支持多种格式输出...`                                                                                                                                                    |
| **股票提槽**   | extract_entities_code（提取实体&代号） | `{"query": "阿里和腾讯哪个更好？和茅台比呢？"}`                            | `[{"entity": "阿里巴巴", "type": "stock", "codes": ["BABA", "09988.HK"]}, {"entity": "腾讯", "type": "stock", "codes": ["00700.HK"]}, {"entity": "茅台", "type": "stock", "codes": ["600519"]}]` |
| **股票基本面**  | akshare_market（实时行情）           | `{"code": "000001"}`                                       | `000001的实时行情: {"代码": "000001", "名称": "平安银行", "最新价": 15.23, "涨跌幅": 2.35, "涨跌额": 0.35, "成交量": 123456, "成交额": 1876543210, "振幅": 3.45, "最高": 15.45, "最低": 14.98, "今开": 15.12, "昨收": 14.88}`  |
|            | crawl_ths_company（公司基本资料）      | `{"query": "详细情况", "code": "000001"}`                      | `平安银行详细情况: 公司成立于1987年，注册资本1000亿元，主营业务为商业银行业务...`                                                                                                                                         |
|            | crawl_ths_holder（股东研究）         | `{"query": "十大股东", "code": "000001"}`                      | `平安银行十大股东: 1.中国平安保险(集团)股份有限公司 58.03%, 2.香港中央结算有限公司 8.12%...`                                                                                                                             |
|            | crawl_ths_operate（经营分析）        | `{"query": "主营业务构成", "code": "000001"}`                    | `平安银行主营业务构成: 利息净收入占比78.5%，手续费及佣金净收入占比15.2%...`                                                                                                                                           |
|            | crawl_ths_equity（股本结构）         | `{"query": "股本构成", "code": "000001"}`                      | `平安银行股本构成: 总股本194.4亿股，其中A股194.4亿股，流通股194.4亿股...`                                                                                                                                         |
|            | crawl_ths_capital（资本运作）        | `{"query": "募集资金", "code": "000001"}`                      | `平安银行募集资金情况: 近期通过定向增发募集资金260亿元，主要用于补充核心一级资本...`                                                                                                                                          |
|            | crawl_ths_finance（财务分析）        | `{"query": "财务指标", "code": "000001"}`                      | `平安银行财务指标: ROE 11.1%，ROA 0.89%，资本充足率13.85%，核心一级资本充足率10.15%...`                                                                                                                           |
|            | crawl_ths_bonus（分红融资）          | `{"query": "分红情况", "code": "000001"}`                      | `平安银行分红情况: 2023年每10股派现2.31元，股息率约1.5%，连续多年稳定分红...`                                                                                                                                        |
|            | crawl_ths_field（行业对比）          | `{"query": "行业地位", "code": "000001"}`                      | `平安银行行业地位: 在股份制银行中排名第3位，资产规模4.9万亿元，市场份额约2.8%...`                                                                                                                                         |
| **股票技术面**  | akshare_calculate（技术分析）        | `{"code": "000001", "query": "最近五日成交量有放量吗？最近五日macd有金叉吗？"}` | `根据分析，该股票最近五日成交量相比前期有明显放量，平均成交量增长35%。MACD指标在最近五日出现金叉信号，DIF线上穿DEA线，显示短期趋势向好。`                                                                                                             |
|            | qtf_brief_mcp（简要分析）            | `{"symbol": "SZ000001"}`                                   | `平安银行(000001)简要分析: 当前股价15.23元，涨幅2.35%。基本面良好，ROE 11.1%，市盈率8.5倍。技术面显示短期趋势向好，建议关注。`                                                                                                         |
|            | qtf_medium_mcp（中等分析）           | `{"symbol": "SZ000001"}`                                   | `平安银行(000001)中等分析: 基本面分析-资产质量稳定，不良率1.02%；盈利能力强，ROE持续改善。技术面分析-MACD金叉，成交量放大，短期支撑位14.8元。估值合理，目标价16.5元。风险提示：银行业监管政策变化。`                                                                      |
|            | qtf_full_mcp（全面分析）             | `{"symbol": "SZ000001"}`                                   | `平安银行(000001)全面分析报告: 1.基本面：资产规模4.9万亿，净利润增长6.8%，ROE 11.1%，资本充足率13.85%。2.技术面：多项指标显示买入信号，支撑阻力位明确。3.估值：PB 0.85倍，PE 8.5倍，相对估值偏低。4.投资建议：买入，目标价16.5-17元，持有期6-12个月。`                             |
|            | crawl_ths_worth（盈利预测）          | `{"query": "业绩预测", "code": "000001"}`                      | `平安银行业绩预测: 2024年预测净利润增长8.5%，ROE预计达到11.2%，机构一致目标价16.5元...`                                                                                                                                |
|            | crawl_ths_position（主力持仓）       | `{"query": "机构持股", "code": "000001"}`                      | `平安银行机构持股: 基金持股占比12.5%，QFII持股占比3.2%，社保基金持股占比1.8%...`                                                                                                                                     |
| **股票消息面**  | crawl_ths_news（新闻公告）           | `{"query": "最新公告", "code": "000001"}`                      | `平安银行最新公告: 发布2024年第三季度业绩报告，净利润同比增长6.8%，不良贷款率1.02%...`                                                                                                                                    |
|            | crawl_ths_concept（概念题材）        | `{"query": "概念板块", "code": "000001"}`                      | `平安银行概念板块: 银行概念、金融科技、数字货币、区块链、人工智能等概念...`                                                                                                                                                |
|            | crawl_ths_event（公司大事）          | `{"query": "高管变动", "code": "000001"}`                      | `平安银行高管变动: 近期董事会决议任命新任副行长，具有20年银行从业经验...`                                                                                                                                                |

### 技术优势

- **高性能**：支持异步处理和并行执行，可处理大规模数据请求
- **高可用**：内置重试机制和异常处理，确保服务稳定性
- **易扩展**：基于插件化架构，可快速添加新的数据源和分析能力
- **标准化**：遵循MCP协议标准，与主流AI平台和工具无缝集成

## basic supply

基础金融供给提供了核心的金融数据获取和分析能力，主要包含以下流程：

| MCP Flow名称            | 能力描述              | Pipeline                                          | 输入示例                                                       | 输出示例                                                                                                                                                                                     |
|-----------------------|-------------------|---------------------------------------------------|------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| extract_entities_code | 从查询中提取金融实体并获取对应代码 | extract_entities_code_op << bailian_web_search_op | `{"query": "阿里和腾讯哪个更好？和茅台比呢？"}`                            | `[{"entity": "阿里巴巴", "type": "stock", "codes": ["BABA", "09988.HK"]}, {"entity": "腾讯", "type": "stock", "codes": ["00700.HK"]}, {"entity": "茅台", "type": "stock", "codes": ["600519"]}]` |
| akshare_market        | 获取A股股票实时行情数据      | akshare_market_op                                 | `{"code": "000001"}`                                       | `000001的实时行情: {"代码": "000001", "名称": "平安银行", "最新价": 15.23, "涨跌幅": 2.35, "涨跌额": 0.35, "成交量": 123456, "成交额": 1876543210, "振幅": 3.45, "最高": 15.45, "最低": 14.98, "今开": 15.12, "昨收": 14.88}`  |
| akshare_calculate     | 基于历史数据进行股票技术分析计算  | akshare_calculate_op                              | `{"code": "000001", "query": "最近五日成交量有放量吗？最近五日macd有金叉吗？"}` | `根据分析，该股票最近五日成交量相比前期有明显放量，平均成交量增长35%。MACD指标在最近五日出现金叉信号，DIF线上穿DEA线，显示短期趋势向好。`                                                                                                             |

### 代码示例

```python
import asyncio
from flowllm.client.fastmcp_client import FastmcpClient


async def basic_supply_example():
    """Basic supply使用示例"""
    async with FastmcpClient(transport="sse", host="11.164.204.33", port=8001) as client:
        # 1. 提取金融实体代码
        print("=== 提取金融实体代码 ===")
        result = await client.call_tool("extract_entities_code", {
            "query": "阿里和腾讯哪个更好？和茅台比呢？"
        })
        print(f"提取结果: {result.content[0].text}")

        # 2. 获取实时行情
        print("\n=== 获取实时行情 ===")
        result = await client.call_tool("akshare_market", {
            "code": "000001"
        })
        print(f"行情数据: {result.content[0].text}")

        # 3. 技术分析计算
        print("\n=== 技术分析计算 ===")
        result = await client.call_tool("akshare_calculate", {
            "code": "000001",
            "query": "最近五日成交量有放量吗？最近五日macd有金叉吗？"
        })
        print(f"分析结果: {result.content[0].text}")


if __name__ == "__main__":
    asyncio.run(basic_supply_example())
```

### 主要特点

- **实体识别**：智能识别查询中的金融实体（股票、基金、ETF等）并自动获取交易代码
- **实时行情**：提供A股市场实时价格、成交量等关键指标
- **技术分析**：基于历史数据进行各类技术指标计算和趋势分析
- **缓存机制**：支持数据缓存以提高查询效率
- **多数据源**：集成akshare和网络搜索能力

### 参考地址

- [akshare](https://github.com/akfamily/akshare)

### 配置地址

- [fin_basic.yaml](../flowllm/config/fin_basic.yaml)

## ths supply

同花顺供给提供了全面的股票深度分析能力，通过爬取同花顺网站获取详细的公司信息和财务数据：

| MCP Flow名称         | 能力描述       | Pipeline                                                         | 输入示例                                    | 输出示例                                                           |
|--------------------|------------|------------------------------------------------------------------|-----------------------------------------|----------------------------------------------------------------|
| crawl_ths_company  | 获取公司基本资料信息 | ths_company_op >> bailian_web_parser_op >> extract_long_text_op  | `{"query": "详细情况", "code": "000001"}`   | `平安银行详细情况: 公司成立于1987年，注册资本1000亿元，主营业务为商业银行业务...`               |
| crawl_ths_holder   | 获取股东研究信息   | ths_holder_op >> bailian_web_parser_op >> extract_long_text_op   | `{"query": "十大股东", "code": "000001"}`   | `平安银行十大股东: 1.中国平安保险(集团)股份有限公司 58.03%, 2.香港中央结算有限公司 8.12%...`   |
| crawl_ths_operate  | 获取经营分析信息   | ths_operate_op >> bailian_web_parser_op >> extract_long_text_op  | `{"query": "主营业务构成", "code": "000001"}` | `平安银行主营业务构成: 利息净收入占比78.5%，手续费及佣金净收入占比15.2%...`                 |
| crawl_ths_equity   | 获取股本结构信息   | ths_equity_op >> bailian_web_parser_op >> extract_long_text_op   | `{"query": "股本构成", "code": "000001"}`   | `平安银行股本构成: 总股本194.4亿股，其中A股194.4亿股，流通股194.4亿股...`               |
| crawl_ths_capital  | 获取资本运作信息   | ths_capital_op >> bailian_web_parser_op >> extract_long_text_op  | `{"query": "募集资金", "code": "000001"}`   | `平安银行募集资金情况: 近期通过定向增发募集资金260亿元，主要用于补充核心一级资本...`                |
| crawl_ths_worth    | 获取盈利预测信息   | ths_worth_op >> bailian_web_parser_op >> extract_long_text_op    | `{"query": "业绩预测", "code": "000001"}`   | `平安银行业绩预测: 2024年预测净利润增长8.5%，ROE预计达到11.2%，机构一致目标价16.5元...`      |
| crawl_ths_news     | 获取新闻公告信息   | ths_news_op >> bailian_web_parser_op >> extract_long_text_op     | `{"query": "最新公告", "code": "000001"}`   | `平安银行最新公告: 发布2024年第三季度业绩报告，净利润同比增长6.8%，不良贷款率1.02%...`          |
| crawl_ths_concept  | 获取概念题材信息   | ths_concept_op >> bailian_web_parser_op >> extract_long_text_op  | `{"query": "概念板块", "code": "000001"}`   | `平安银行概念板块: 银行概念、金融科技、数字货币、区块链、人工智能等概念...`                      |
| crawl_ths_position | 获取主力持仓信息   | ths_position_op >> bailian_web_parser_op >> extract_long_text_op | `{"query": "机构持股", "code": "000001"}`   | `平安银行机构持股: 基金持股占比12.5%，QFII持股占比3.2%，社保基金持股占比1.8%...`           |
| crawl_ths_finance  | 获取财务分析信息   | ths_finance_op >> bailian_web_parser_op >> extract_long_text_op  | `{"query": "财务指标", "code": "000001"}`   | `平安银行财务指标: ROE 11.1%，ROA 0.89%，资本充足率13.85%，核心一级资本充足率10.15%...` |
| crawl_ths_bonus    | 获取分红融资信息   | ths_bonus_op >> bailian_web_parser_op >> extract_long_text_op    | `{"query": "分红情况", "code": "000001"}`   | `平安银行分红情况: 2023年每10股派现2.31元，股息率约1.5%，连续多年稳定分红...`              |
| crawl_ths_event    | 获取公司大事信息   | ths_event_op >> bailian_web_parser_op >> extract_long_text_op    | `{"query": "高管变动", "code": "000001"}`   | `平安银行高管变动: 近期董事会决议任命新任副行长，具有20年银行从业经验...`                      |
| crawl_ths_field    | 获取行业对比信息   | ths_field_op >> bailian_web_parser_op >> extract_long_text_op    | `{"query": "行业地位", "code": "000001"}`   | `平安银行行业地位: 在股份制银行中排名第3位，资产规模4.9万亿元，市场份额约2.8%...`               |

### 数据来源

- [来源地址](https://basic.10jqka.com.cn/300033/)
- 同花顺基本面数据
- 公司资料、股东信息、经营分析
- 股本结构、资本运作、盈利预测
- 新闻公告、概念题材、主力持仓
- 财务分析、分红融资、公司大事
- 行业对比等全方位数据

### 代码示例

```python
import asyncio
from flowllm.client.fastmcp_client import FastmcpClient


async def ths_supply_example():
    """THS supply使用示例"""
    async with FastmcpClient(transport="sse", host="11.164.204.33", port=8001) as client:

        # 示例股票代码
        stock_code = "000001"  # 平安银行

        # 1. 获取公司基本资料信息
        print("=== 公司基本资料 ===")
        result = await client.call_tool("crawl_ths_company", {
            "query": "平安银行的公司情况如何？",
            "code": stock_code
        })
        print(f"公司信息: {result.content[0].text}")

        # 2. 获取股东研究信息
        print("\n=== 股东研究 ===")
        result = await client.call_tool("crawl_ths_holder", {
            "query": "平安银行的股东结构如何？",
            "code": stock_code
        })
        print(f"股东信息: {result.content[0].text}")

        # 3. 获取经营分析信息
        print("\n=== 经营分析 ===")
        result = await client.call_tool("crawl_ths_operate", {
            "query": "平安银行的主营业务是什么？",
            "code": stock_code
        })
        print(f"经营信息: {result.content[0].text}")

        # 4. 获取财务分析信息
        print("\n=== 财务分析 ===")
        result = await client.call_tool("crawl_ths_finance", {
            "query": "平安银行的财务状况如何？",
            "code": stock_code
        })
        print(f"财务信息: {result.content[0].text}")

        # 5. 获取新闻公告信息
        print("\n=== 新闻公告 ===")
        result = await client.call_tool("crawl_ths_news", {
            "query": "平安银行最近有什么新闻？",
            "code": stock_code
        })
        print(f"新闻信息: {result.content[0].text}")

        # 6. 获取概念题材信息
        print("\n=== 概念题材 ===")
        result = await client.call_tool("crawl_ths_concept", {
            "query": "平安银行涉及哪些概念题材？",
            "code": stock_code
        })
        print(f"概念信息: {result.content[0].text}")

        # 7. 获取主力持仓信息
        print("\n=== 主力持仓 ===")
        result = await client.call_tool("crawl_ths_position", {
            "query": "平安银行的机构持仓情况如何？",
            "code": stock_code
        })
        print(f"持仓信息: {result.content[0].text}")

        # 8. 其他维度信息示例
        other_examples = [
            ("crawl_ths_equity", {"query": "股本结构如何？", "code": stock_code}),
            ("crawl_ths_capital", {"query": "有哪些资本运作？", "code": stock_code}),
            ("crawl_ths_worth", {"query": "业绩预测如何？", "code": stock_code}),
            ("crawl_ths_bonus", {"query": "分红情况如何？", "code": stock_code}),
            ("crawl_ths_event", {"query": "最近有什么重大事件？", "code": stock_code}),
            ("crawl_ths_field", {"query": "在行业中的地位如何？", "code": stock_code})
        ]

        for tool_name, params in other_examples:
            print(f"\n=== {tool_name} ===")
            try:
                result = await client.call_tool(tool_name, params)
                print(f"结果: {result.content[0].text[:200]}...")
            except Exception as e:
                print(f"调用失败: {e}")


if __name__ == "__main__":
    asyncio.run(ths_supply_example())
```

### 配置地址

- [fin_ths.yaml](../flowllm/config/fin_ths.yaml)

## mcp supply

MCP供给提供了基于阿里云百炼平台的量化投资分析能力，通过qtf_mcp工具提供不同深度的股票分析服务：

| MCP Flow名称     | 能力描述       | Pipeline          | 输入示例                     | 输出示例                                                                                                                                                         |
|----------------|------------|-------------------|--------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| qtf_brief_mcp  | 提供股票基础分析摘要 | qtf_brief_mcp_op  | `{"symbol": "SZ000001"}` | `平安银行(000001)简要分析: 当前股价15.23元，涨幅2.35%。基本面良好，ROE 11.1%，市盈率8.5倍。技术面显示短期趋势向好，建议关注。`                                                                             |
| qtf_medium_mcp | 提供股票中等深度分析 | qtf_medium_mcp_op | `{"symbol": "SZ000001"}` | `平安银行(000001)中等分析: 基本面分析-资产质量稳定，不良率1.02%；盈利能力强，ROE持续改善。技术面分析-MACD金叉，成交量放大，短期支撑位14.8元。估值合理，目标价16.5元。风险提示：银行业监管政策变化。`                                          |
| qtf_full_mcp   | 提供股票全面深度分析 | qtf_full_mcp_op   | `{"symbol": "SZ000001"}` | `平安银行(000001)全面分析报告: 1.基本面：资产规模4.9万亿，净利润增长6.8%，ROE 11.1%，资本充足率13.85%。2.技术面：多项指标显示买入信号，支撑阻力位明确。3.估值：PB 0.85倍，PE 8.5倍，相对估值偏低。4.投资建议：买入，目标价16.5-17元，持有期6-12个月。` |

### 代码示例

```python
import asyncio
from flowllm.client.fastmcp_client import FastmcpClient


async def mcp_supply_example():
    """MCP supply使用示例"""
    async with FastmcpClient(transport="sse", host="11.164.204.33", port=8001) as client:
        # 1. 简要分析
        print("=== 股票简要分析 ===")
        result = await client.call_tool("qtf_brief_mcp", {
            "symbol": "SZ000001"
        })
        print(f"简要分析: {result.content[0].text}")

        # 2. 中等深度分析
        print("\n=== 股票中等深度分析 ===")
        result = await client.call_tool("qtf_medium_mcp", {
            "symbol": "SZ000001"
        })
        print(f"中等分析: {result.content[0].text}")

        # 3. 全面深度分析
        print("\n=== 股票全面深度分析 ===")
        result = await client.call_tool("qtf_full_mcp", {
            "symbol": "SZ000001"
        })
        print(f"全面分析: {result.content[0].text}")


if __name__ == "__main__":
    asyncio.run(mcp_supply_example())
```

### 主要特点

- **brief模式**：提供股票的基础信息和简要分析结论，适合快速了解
- **medium模式**：包含基本面、技术面和估值的中等深度分析，平衡详细度和效率
- **full模式**：提供全面深度的投资分析报告，包含详细的投资建议和风险提示

### 数据来源

- [阿里云百炼MCP市场](https://bailian.console.aliyun.com/pre-publish?tab=mcp#/mcp-market/detail/qtf_mcp)

### 配置地址

- [fin_mcp.yaml](../flowllm/config/fin_mcp.yaml)

## ant supply

| MCP Flow名称     | Pipeline          | 输入示例                                            | 输出示例                  |
|----------------|-------------------|-------------------------------------------------|-----------------------|
| ant_search     | ant_search_op     | `{"query": "平安银行最新财报分析"}`                       | `平安银行2024年Q3财报显示：...` |
| ant_investment | ant_investment_op | `{"entity": "阿里巴巴", "analysis_category": "股票"}` | `阿里巴巴投资分析：...`        |

### 配置地址

- [fin_ant.yaml](../flowllm/config/fin_ant.yaml)

## search supply

搜索供给提供了多样化的网络搜索和内容解析能力，集成了多个优质搜索引擎和解析工具：

| MCP Flow名称         | Pipeline                                 | 输入示例                                   | 输出示例                                                        |
|--------------------|------------------------------------------|----------------------------------------|-------------------------------------------------------------|
| tavily_search      | tavily_search_op >> extract_long_text_op | `{"query": "2024年中国GDP增长情况"}`          | `根据最新数据，2024年中国GDP同比增长5.2%，经济运行总体平稳，消费和投资成为主要增长动力...`       |
| dashscope_search   | dashscope_search_op                      | `{"query": "人工智能最新发展趋势"}`              | `人工智能领域最新发展包括大语言模型技术突破、多模态AI应用普及、AI+行业深度融合等趋势...`           |
| bailian_web_search | bailian_web_search_op                    | `{"query": "新能源汽车市场现状", "count": 10}`  | `2024年新能源汽车市场保持高速增长，销量突破800万辆，市场渗透率达到35%，比亚迪、特斯拉领跑市场...`    |
| bocha_web_search   | bocha_web_search_op                      | `{"query": "区块链技术应用", "freshness": 7}` | `区块链技术在金融、供应链、数字身份等领域应用不断深化，央行数字货币DCEP试点扩大，DeFi生态持续发展...`   |
| brave_web_search   | brave_web_search_op                      | `{"query": "量子计算突破", "count": 5}`      | `量子计算领域取得重大突破，IBM发布1000+量子比特处理器，Google实现量子纠错里程碑，产业化进程加速...` |
| bailian_web_parser | bailian_web_parser_op                    | `{"url": "https://example.com"}`       | `解析网页内容：标题、正文、关键信息等结构化数据，支持多种格式输出...`                       |

### 代码示例

```python
import asyncio
from flowllm.client.fastmcp_client import FastmcpClient


async def search_supply_example():
    """Search supply使用示例"""
    async with FastmcpClient(transport="sse", host="11.164.204.33", port=8001) as client:
        # 1. Tavily搜索（带长文本提取）
        print("=== Tavily搜索 ===")
        result = await client.call_tool("tavily_search", {
            "query": "2024年中国GDP增长情况"
        })
        print(f"搜索结果: {result.content[0].text}")

        # 2. 通义搜索
        print("\n=== 通义搜索 ===")
        result = await client.call_tool("dashscope_search", {
            "query": "人工智能最新发展趋势"
        })
        print(f"搜索结果: {result.content[0].text}")

        # 3. 百炼网络搜索（带数量限制）
        print("\n=== 百炼网络搜索 ===")
        result = await client.call_tool("bailian_web_search", {
            "query": "新能源汽车市场现状",
            "count": 10
        })
        print(f"搜索结果: {result.content[0].text}")

        # 4. Bocha搜索（带时效性）
        print("\n=== Bocha搜索 ===")
        result = await client.call_tool("bocha_web_search", {
            "query": "区块链技术应用",
            "freshness": 7
        })
        print(f"搜索结果: {result.content[0].text}")

        # 5. Brave搜索
        print("\n=== Brave搜索 ===")
        result = await client.call_tool("brave_web_search", {
            "query": "量子计算突破",
            "count": 5
        })
        print(f"搜索结果: {result.content[0].text}")

        # 6. 网页内容解析
        print("\n=== 网页内容解析 ===")
        result = await client.call_tool("bailian_web_parser", {
            "url": "https://basic.10jqka.com.cn/601899/field.html"
        })
        print(f"解析结果: {result.content[0].text}")


if __name__ == "__main__":
    asyncio.run(search_supply_example())
```

### 配置地址

- [fin_search.yaml](../flowllm/config/fin_search.yaml)