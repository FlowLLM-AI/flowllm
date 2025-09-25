# 🔬 Deep Research Guide

FlowLLM 提供多种深度研究能力，支持不同的搜索后端和研究模式。

## 📊 可用的研究流程

| 流程名称                             | 描述                      | 特点               |
|----------------------------------|-------------------------|------------------|
| `dashscope_deep_research`        | DashScope 原生深度研究        | 快速研究，内置搜索优化      |
| `langchain+brief+bailian_search` | LangChain + 百炼搜索 + 研究摘要 | 全面研究，话题转换，详细报告   |
| `langchain+brief+bocha_search`   | LangChain + 博查搜索 + 研究摘要 | 全面研究，替代搜索引擎，详细报告 |
| `langchain+bailian_search`       | LangChain + 百炼搜索        | 直接研究，流程简化，执行快速   |
| `langchain+bocha_search`         | LangChain + 博查搜索        | 直接研究，替代搜索源，执行快速  |

## 💻 使用方法

以下是各个研究流程的调用方式：

**1. DashScope 深度研究**

```bash
curl -X POST http://11.164.204.33:8002/dashscope_deep_research -H "Content-Type: application/json" -d '{"query": "什么是人工智能？"}'
```

**2. LangChain + 研究摘要 + 百炼搜索**

```bash
curl -X POST http://11.164.204.33:8002/langchain+brief+bailian_search -H "Content-Type: application/json" -d '{"query": "分析2025年电动汽车的竞争格局"}'
```

**3. LangChain + 研究摘要 + 博查搜索**

```bash
curl -X POST http://11.164.204.33:8002/langchain+brief+bocha_search -H "Content-Type: application/json" -d '{"query": "量子计算的最新发展是什么？"}'
```

**4. LangChain + 百炼搜索**

```bash
curl -X POST http://11.164.204.33:8002/langchain+bailian_search -H "Content-Type: application/json" -d '{"query": "比较全球可再生能源的采用率"}'
```

**5. LangChain + 博查搜索**

```bash
curl -X POST http://11.164.204.33:8002/langchain+bocha_search -H "Content-Type: application/json" -d '{"query": "区块链技术的当前趋势是什么？"}'
```

**6. query合成**

```bash
curl -X POST http://11.164.204.33:8002/task_react -H "Content-Type: application/json" -d '{"items": ["", ""]}'
```

items: list of input_topic(str), e.g. ["", ""] or ["行业研究","行业研究","个股分析"]，不写就是在这几个中随机

增加`exist_list`参数告诉模型之前产出了哪些query，避免重复