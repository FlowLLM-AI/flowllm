### MCP API调用示例

标准的MCP服务使用方法，参考 [mcp_supply_test.py](../test/mcp_supply_test.py)

## MCP工具的HTTP API调用示例

以下是每个MCP工具对应的curl命令示例，部署在8002端口，用于HTTP API测试：

### 1. Ant

```bash
curl -X POST http://11.164.204.33:8002/ant_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "紫金怎么样？雪球",
    "entity": "紫金"
  }'

curl -X POST http://11.164.204.33:8002/ant_investment \
  -H "Content-Type: application/json" \
  -d '{
    "entity": "阿里巴巴",
    "analysis_category": "股票"
  }'
```

### 2. 搜索引擎工具

```bash
# tavily_search - Tavily搜索
curl -X POST http://11.164.204.33:8002/tavily_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "紫金怎么样？雪球"
  }'

# dashscope_search - DashScope搜索
curl -X POST http://11.164.204.33:8002/dashscope_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "紫金怎么样？雪球"
  }'

# brave_web_search - Brave网页搜索
curl -X POST http://11.164.204.33:8002/brave_web_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "紫金怎么样？雪球"
  }'

# bailian_web_search - 百炼网页搜索
curl -X POST http://11.164.204.33:8002/bailian_web_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "紫金怎么样？雪球"
  }'

# bocha_web_search - 博茶网页搜索
curl -X POST http://11.164.204.33:8002/bocha_web_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "紫金怎么样？雪球"
  }'
```

### 3. 网页解析工具

```bash
# bailian_web_parser - 百炼网页解析
curl -X POST http://11.164.204.33:8002/bailian_web_parser \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://basic.10jqka.com.cn/601899/field.html"
  }'

# 解析公司信息页面
curl -X POST http://11.164.204.33:8002/bailian_web_parser \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://basic.10jqka.com.cn/601899/company.html"
  }'
```

### 4. 实体提取工具

```bash
# extract_entities_code - 实体代码提取
curl -X POST http://11.164.204.33:8002/extract_entities_code \
  -H "Content-Type: application/json" \
  -d '{
    "query": "阿里和腾讯哪个更好？和茅台比呢？"
  }'
```

### 5. AKShare市场数据工具

```bash
# akshare_market - AKShare市场数据
curl -X POST http://11.164.204.33:8002/akshare_market \
  -H "Content-Type: application/json" \
  -d '{
    "code": "000001"
  }'

# akshare_calculate - AKShare计算分析
curl -X POST http://11.164.204.33:8002/akshare_calculate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行最近行情走势",
    "code": "000001"
  }'
```

### 6. QTF量化工具

```bash
# qtf_brief_mcp - QTF简要信息
curl -X POST http://11.164.204.33:8002/qtf_brief_mcp \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "SZ000001"
  }'

# qtf_medium_mcp - QTF中等详细信息
curl -X POST http://11.164.204.33:8002/qtf_medium_mcp \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "SZ000001"
  }'

# qtf_full_mcp - QTF完整信息
curl -X POST http://11.164.204.33:8002/qtf_full_mcp \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "SZ000001"
  }'
```

### 7. 同花顺(THS)数据爬取工具

```bash
# crawl_ths_company - 爬取公司基本信息
curl -X POST http://11.164.204.33:8002/crawl_ths_company \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行的公司情况如何？",
    "code": "000001"
  }'

# crawl_ths_holder - 爬取股东结构信息
curl -X POST http://11.164.204.33:8002/crawl_ths_holder \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行的股东结构如何？",
    "code": "000001"
  }'

# crawl_ths_operate - 爬取主营业务信息
curl -X POST http://11.164.204.33:8002/crawl_ths_operate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行的主营业务是什么？",
    "code": "000001"
  }'

# crawl_ths_equity - 爬取股本结构信息
curl -X POST http://11.164.204.33:8002/crawl_ths_equity \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行的股本结构如何？",
    "code": "000001"
  }'

# crawl_ths_capital - 爬取资本运作信息
curl -X POST http://11.164.204.33:8002/crawl_ths_capital \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行有哪些资本运作？",
    "code": "000001"
  }'

# crawl_ths_worth - 爬取业绩预测信息
curl -X POST http://11.164.204.33:8002/crawl_ths_worth \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行的业绩预测如何？",
    "code": "000001"
  }'

# crawl_ths_news - 爬取最新新闻
curl -X POST http://11.164.204.33:8002/crawl_ths_news \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行最近有什么新闻？",
    "code": "000001"
  }'

# crawl_ths_concept - 爬取概念题材信息
curl -X POST http://11.164.204.33:8002/crawl_ths_concept \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行涉及哪些概念题材？",
    "code": "000001"
  }'

# crawl_ths_position - 爬取机构持仓信息
curl -X POST http://11.164.204.33:8002/crawl_ths_position \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行的机构持仓情况如何？",
    "code": "000001"
  }'

# crawl_ths_finance - 爬取财务状况信息
curl -X POST http://11.164.204.33:8002/crawl_ths_finance \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行的财务状况如何？",
    "code": "000001"
  }'

# crawl_ths_bonus - 爬取分红情况信息
curl -X POST http://11.164.204.33:8002/crawl_ths_bonus \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行的分红情况如何？",
    "code": "000001"
  }'

# crawl_ths_event - 爬取重大事件信息
curl -X POST http://11.164.204.33:8002/crawl_ths_event \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行最近有什么重大事件？",
    "code": "000001"
  }'

# crawl_ths_field - 爬取行业地位信息
curl -X POST http://11.164.204.33:8002/crawl_ths_field \
  -H "Content-Type: application/json" \
  -d '{
    "query": "平安银行在行业中的地位如何？",
    "code": "000001"
  }'
```

### 8. 其他股票代码示例

```bash
# 紫金矿业公司信息
curl -X POST http://11.164.204.33:8002/crawl_ths_company \
  -H "Content-Type: application/json" \
  -d '{
    "query": "紫金矿业的公司情况如何？",
    "code": "601899"
  }'

# 紫金矿业财务指标
curl -X POST http://11.164.204.33:8002/crawl_ths_finance \
  -H "Content-Type: application/json" \
  -d '{
    "query": "紫金矿业的财务指标怎么样？",
    "code": "601899"
  }'
```

