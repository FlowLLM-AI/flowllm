## background

## basic supply

基础金融供给提供了核心的金融数据获取和分析能力，主要包含以下流程：

| MCP Flow名称            | 能力描述              | Pipeline                                          | 输入示例                                                       | 输出示例                                                                                                                                                                                     |
|-----------------------|-------------------|---------------------------------------------------|------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| extract_entities_code | 从查询中提取金融实体并获取对应代码 | extract_entities_code_op << bailian_web_search_op | `{"query": "阿里和腾讯哪个更好？和茅台比呢？"}`                            | `[{"entity": "阿里巴巴", "type": "stock", "codes": ["BABA", "09988.HK"]}, {"entity": "腾讯", "type": "stock", "codes": ["00700.HK"]}, {"entity": "茅台", "type": "stock", "codes": ["600519"]}]` |
| akshare_market        | 获取A股股票实时行情数据      | akshare_market_op                                 | `{"code": "000001"}`                                       | `000001的实时行情: {"代码": "000001", "名称": "平安银行", "最新价": 15.23, "涨跌幅": 2.35, "涨跌额": 0.35, "成交量": 123456, "成交额": 1876543210, "振幅": 3.45, "最高": 15.45, "最低": 14.98, "今开": 15.12, "昨收": 14.88}`  |
| akshare_calculate     | 基于历史数据进行股票技术分析计算  | akshare_calculate_op                              | `{"code": "000001", "query": "最近五日成交量有放量吗？最近五日macd有金叉吗？"}` | `根据分析，该股票最近五日成交量相比前期有明显放量，平均成交量增长35%。MACD指标在最近五日出现金叉信号，DIF线上穿DEA线，显示短期趋势向好。`                                                                                                             |

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

### 主要特点

- **全面覆盖**：涵盖公司基本面、财务、股东、经营等13个维度的深度信息
- **实时爬取**：直接从同花顺官网获取最新数据，确保信息时效性
- **智能解析**：使用百炼网页解析器提取结构化信息
- **缓存优化**：支持数据缓存机制，提高查询效率
- **灵活查询**：支持针对性查询，根据用户问题返回相关信息

### 数据来源

- 来源地址: https://basic.10jqka.com.cn/300033/
- 同花顺基本面数据
- 公司资料、股东信息、经营分析
- 股本结构、资本运作、盈利预测
- 新闻公告、概念题材、主力持仓
- 财务分析、分红融资、公司大事
- 行业对比等全方位数据

### 配置地址

- [fin_ths.yaml](../flowllm/config/fin_ths.yaml)

## mcp supply

## ant supply

## search supply