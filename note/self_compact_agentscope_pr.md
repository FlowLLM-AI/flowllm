# SELFCOMPACT 论文与 AgentScope PR 技术解读

---

## 1. 论文要解决的问题

长任务 Agent 的轨迹通常包含：

- 多轮 reasoning；
- 工具调用和工具返回；
- 中间搜索结果；
- 已经失败或过期的假设；
- 局部结论和待验证事实。

这些内容持续累积后会产生两个问题：

1. **上下文窗口溢出**

   轨迹最终超过模型上下文窗口，系统必须截断、压缩或停止。

2. **context rot**

   论文强调的重点不是单纯 token 不够，而是旧的、错误的、低价值的上下文会锚定后续生成。模型在干净上下文里能解决的问题，喂回自己早期错误推理后反而可能失败。

现有系统通常使用固定规则压缩：

| 策略                  | 触发方式               | 问题                        |
|---------------------|--------------------|---------------------------|
| Reactive compaction | 快到上下文上限时压缩         | 太晚，污染上下文已经影响了很多步          |
| Periodic compaction | 每隔固定 token/turn 压缩 | 不看任务状态，可能在推导中间、搜索中间压掉关键内容 |
| 手动 `/compact`       | 用户决定               | 把识别 context rot 的负担交给用户   |

论文的核心判断是：**什么时候压缩，取决于轨迹结构，而不只是 token 数。**

---

## 2. SELFCOMPACT 的核心机制

SELFCOMPACT 是一个训练无关的 scaffold，不改模型权重。它由两个推理时元素组成：

1. **压缩工具**

   模型可以触发一个 summarizer，把当前累计轨迹压成摘要，然后系统用摘要替换旧轨迹，后续从摘要继续。

2. **rubric 判定**

   系统定期向同一个模型追加一个轻量判断 prompt，让模型输出 `COMPRESS` 或 `CONTINUE`。rubric 明确告诉模型什么情况下可以压缩、什么情况下不能压缩。

论文的关键结论是：**工具和 rubric 必须同时存在。**

- 只有工具：不同模型行为不稳定，有的乱压，有的不压。
- 只有 rubric：只能判断，不能改变上下文。
- 工具 + rubric：在合适的 closed reasoning unit 后压缩，避免在 mid-derivation 或 stuck 状态压缩。

### 2.1 算法流程

论文 Algorithm 1 可以简化为：

```text
C = original_prompt

for each generation step:
    y = model(C)
    C = C + y

    if y is final answer:
        return y

    if reach probe interval:
        C_probe = C + rubric_prompt
        decision = model(C_probe)  # COMPRESS or CONTINUE

        if decision == COMPRESS:
            C_sum = C + summarizer_prompt
            summary = model(C_sum)
            C = original_prompt + summary
        else:
            discard rubric prompt and decision
            continue with original C
```

几个实现要点：

- rubric probe 是追加到现有上下文上的，不替换上下文；
- `CONTINUE` 时，rubric prompt 和判定结果会被移除，不污染真实轨迹；
- `COMPRESS` 时，summarizer 输出摘要，旧轨迹被摘要替换；
- rubric judge 和 summarizer 都使用同一个模型，不引入外部 verifier；
- 通过追加 prompt 复用已有 KV cache，避免每次判定都重新 prefill 整个长轨迹。

---

## 3. Rubric 的设计

论文不是用一个泛化口号式 prompt，而是针对任务类型设计 rubric。

### 3.1 数学任务 rubric

数学任务在每个 round 边界检查三个问题：

| 问题            | 含义                                          |
|---------------|---------------------------------------------|
| `Q1 ANSWER`   | 最新 round 是否给出了明确 final answer，比如 `\boxed{}` |
| `Q2 STUCK`    | 最近 2 个 round 是否没有新增非平凡事实                    |
| `Q3 HAS-NEXT` | 是否能写出明确下一步，例如 case split、substitution、lemma |

触发规则：

```text
COMPRESS iff Q1 = Y or (Q2 = Y and Q3 = Y)
```

直觉：

- 已经有答案时，压缩可以锁定结果，后续验证或改进。
- 卡住但有明确下一步时，压缩可以丢掉无效循环，保留下一步方向。
- 如果还在活跃推导中，不能压缩。

### 3.2 搜索任务 rubric

Agentic search 的 rubric 更严格，要求四个门同时满足：

| 条件                | 含义                                           |
|-------------------|----------------------------------------------|
| `C1 CLOSED-UNIT`  | 最近消息是完整工具调用结果或完整子分析，不是半截思路                   |
| `C2 SUMMARIZABLE` | 关键信息可以压成 3-5 条带引用事实                          |
| `C3 PROGRESS`     | 自上次压缩后确实有新事实或新子问题                            |
| `N1 STUCK`        | 是否卡住，如果最近 4 次搜索中至少 3 次没有新 URL 或新事实，则视为 stuck |

触发规则：

```text
COMPRESS iff C1 = Y and C2 = Y and C3 = Y and N1 = N
```

这组条件体现了论文的主要工程思想：

- 压缩应该发生在“阶段结束后”；
- 需要保留的内容必须能被摘要可靠表达；
- 没有新进展就不要反复压缩；
- 卡住时压缩可能掩盖问题，不能把 dead ends 总结成看似有用的状态。

---

## 4. Summarizer 的设计

论文里的 summarizer 不是普通闲聊摘要，而是 continuation summary：摘要要替代完整历史，让模型继续完成任务。

### 4.1 数学摘要

数学 summarizer 要求：

- 保留关键洞察、重要计算、推理路径；
- 删除重复文本、失败尝试和无意义重复；
- 如果找到了 final answer，必须保留；
- 如果答案可能错误或未验证，需要标注仍需验证；
- 输出未完成部分需要继续做什么。

### 4.2 搜索摘要

搜索 summarizer 要求：

- 只提取对回答原问题直接有用的信息；
- 不做超出对话内容的推断；
- 不保留不确定或无法确认的信息；
- 把多轮搜索里的确定事实合成为可继续研究的状态。

这和固定阈值摘要的区别在于：SELFCOMPACT 先判断“现在是否适合压缩”，再调用 summarizer；不是 summarizer 自己承担所有风险。

---

## 5. 实验设计

论文覆盖 6 个 benchmark、7 个模型，分为两类任务。

### 5.1 竞争数学

模型：

- Qwen3-4B-Instruct-2507
- Qwen3-30B-A3B-Instruct-2507
- Qwen3.5-4B
- Qwen3.5-9B

Benchmark：

- IMO-Answerbench
- HMMT Nov 2025
- HMMT Feb 2026

对比方法：

| 方法                     | 说明                              |
|------------------------|---------------------------------|
| No Compaction          | 单次 16k token 预算，不压缩             |
| Fixed Interval Summary | 每 16,384 generated tokens 后强制摘要 |
| SELFCOMPACT            | 根据 rubric 判断是否摘要                |

设置：

- 每题生成 16 个样本；
- temperature 1.0，top-p 0.7；
- summarizer 输出硬截断 512 tokens；
- fixed interval 的 token 预算和 SELFCOMPACT 匹配，避免因为 token 更多而不公平。

### 5.2 Agentic search

模型：

- GLM-4.7-Flash
- MiniMax-M2.5
- MiMo-V2-Flash

Benchmark：

- BrowseComp
- BrowseComp-Plus
- DeepSearchQA

对比方法：

| 方法                     | 说明                               |
|------------------------|----------------------------------|
| No Compaction          | 不做上下文管理，直到窗口或工具调用上限              |
| Fixed-interval summary | prompt 达到 30% context window 后摘要 |
| Delete-all             | 达到 30% 后删除全部历史                   |
| Keep-last-N            | 达到 30% 后只保留最后 3 turn             |
| SELFCOMPACT            | rubric 判定后摘要                     |

搜索任务还加了工程 gate：

- 至少第 3 轮后才允许检查；
- prompt 至少 40,000 tokens；
- 最多摘要 1 次；
- 距离上次 probe 至少 2 轮；
- 达到 30% context window 时有 backstop 强制压缩。

---

## 6. 实验结果

### 6.1 数学任务

论文 Table 1 的总体结论：

- 在 12 个模型/benchmark 组合中，SELFCOMPACT 在 11 个组合上最好；
- 对 thinking-disabled 的 Qwen3.5 系列提升尤其明显；
- Qwen3.5-9B 上相对 No Compaction 的提升达到：
    - IMO-Answerbench：+16.4
    - HMMT Nov：+10.0
    - HMMT Feb：+18.1

平均准确率可以概括为：

| 模型                     | No Compaction | Fixed Interval | SELFCOMPACT |
|------------------------|--------------:|---------------:|------------:|
| Qwen3-4B-Instruct      |          38.7 |           41.5 |        45.1 |
| Qwen3-30B-A3B-Instruct |          50.6 |           54.9 |        56.4 |
| Qwen3.5-9B             |          32.5 |           40.1 |        47.3 |
| Qwen3.5-4B             |          21.9 |           30.7 |        33.8 |

重要的是，Fixed Interval 并非无效，它通常比 No Compaction 好；但它会在错误时机压缩，留下进一步提升空间。

论文还做了 oracle 分析：如果固定间隔摘要在“当前答案已经正确”时跳过压缩，IMO-Answerbench 上 Qwen3-4B-Instruct 可以从 41.4
提升到 52.9。这说明固定间隔压缩确实经常破坏已经正确的状态。

### 6.2 Agentic search

论文 Table 4 的结论：

- SELFCOMPACT 在三个模型上 overall accuracy 都最高；
- BrowseComp-Plus 上相对 No Compaction 的提升：
    - GLM-4.7-Flash：+8.5
    - MiniMax-M2.5：+9.2
    - MiMo-V2-Flash：+5.3
- 成本反而低于 No Compaction，因为摘要后后续 prompt 变短。

Overall 结果：

| 模型            | No Compaction | Fixed Interval |  SELFCOMPACT |
|---------------|--------------:|---------------:|-------------:|
| GLM-4.7-Flash |  36.6 / $0.13 |   41.5 / $0.05 | 46.4 / $0.07 |
| MiniMax-M2.5  |  54.6 / $0.19 |   59.3 / $0.06 | 63.9 / $0.08 |
| MiMo-V2-Flash |  48.9 / $0.25 |   54.7 / $0.14 | 59.2 / $0.13 |

这里有一个细节：SELFCOMPACT 不一定总比 Fixed Interval 更便宜，但通常在准确率上更强，并且相对 No Compaction 有明显成本下降。

### 6.3 压缩触发时机

论文 Figure 2 显示：

- Fixed Interval 的触发点固定在 30% context window；
- SELFCOMPACT 的触发点分布更靠左，也更分散；
- 这说明很多情况下，模型在到达 30% 阈值之前已经完成了一个可压缩阶段。

这支持论文主张：固定阈值通常太晚，已经让 stale tokens 多污染了若干步。

### 6.4 难题收益更明显

论文 Figure 3 用 No Compaction 的输出 token 数作为难度 proxy，把题目分成 5 个 quantile。

结果：

- 简单题上，各策略差距不大；
- 最难的两个区间，SELFCOMPACT 比固定阈值高 5-20 个百分点；
- 越需要长搜索、越容易累积错误上下文，rubric-gated 压缩越有价值。

### 6.5 Rubric 消融

论文做了去掉 rubric 的消融，让模型自己决定是否摘要。

| 任务             | Fixed Interval | SELFCOMPACT w/o rubrics | SELFCOMPACT |
|----------------|---------------:|------------------------:|------------:|
| GLM search avg |           41.5 |                    41.0 |        46.4 |
| Qwen3-4B IMO   |           41.4 |                    40.9 |        45.5 |

结论很直接：收益不是来自“能压缩”本身，而是来自 rubric 对压缩时机的约束。

---

## 7. 成本分析

SELFCOMPACT 每次 probe 最多增加两个 LLM call：

1. rubric probe；
2. 如果判定为 `COMPRESS`，再调用 summarizer。

论文认为这个额外成本可控，原因是：

- probe 和 summarizer 都是追加到已有 prefix 上，能复用 KV cache；
- rubric 只生成很短的判定；
- 真正的收益来自压缩后每个后续调用的 prompt 都变短。

论文给出的经验压缩比：

```text
50k-100k trajectory -> 1k-3k summary
```

也就是 20-80 倍缩短。只要后续还有多轮调用，摘要成本很容易被摊销。

---

## 8. 定性案例

论文附录 E 展示了 3 个 BrowseComp-Plus case，重点不是“压缩是否发生”，而是“压缩发生在什么状态”。

### 8.1 Whitesnake

Fixed Interval：

- 每次 30% 阈值触发摘要；
- 摘要反复保留同一批错误候选；
- Agent 一直被错误 shortlist 锚定，最终猜错。

SELFCOMPACT：

- rubric 在没有 closed unit 时继续；
- 等到约 118k tokens 后做一次压缩；
- 摘要保留约束而不是错误候选列表；
- Agent 跳出旧候选，找到 David Coverdale 和 Whitesnake。

### 8.2 Majida El Roumi

Fixed Interval：

- 早期误把 classical piece 线索引到 Rachmaninoff；
- 每次摘要都把错误 lead 带下去；
- 最后没有测试 Arabic artist。

SELFCOMPACT：

- 先继续搜索，直到修正为 Albinoni's Adagio；
- 在 corrected lead 后压缩；
- 后续定位 Majida El Roumi。

### 8.3 Raheem Sterling

Fixed Interval：

- 搜索 goal-minute fingerprint 无果；
- 摘要不断重放同一批无效搜索日志；
- 没有测试 Tottenham vs Chelsea。

SELFCOMPACT：

- 允许继续探索直到找到正确 match；
- match 找到后压缩；
- 后续验证 attendance、进球和助攻，得到 Raheem Sterling。

这些 case 说明：不合时机的摘要会把错误路径固化；合时机的摘要可以把阶段性事实固化，并让模型从无效循环中脱离。

---

## 9. AgentScope PR #1938 实现

PR #1938 把 SELFCOMPACT 的思想接到 AgentScope 的上下文压缩逻辑里。改动集中在三个文件：

| 文件                                | 改动                                 |
|-----------------------------------|------------------------------------|
| `src/agentscope/agent/_agent.py`  | 在压缩流程中加入 self-compaction 判定        |
| `src/agentscope/agent/_config.py` | 增加 self-compaction 配置和结构化输出 schema |
| `tests/compress_context_test.py`  | 增加默认关闭、提前压缩、跳过、失败容错等测试             |

### 9.1 新增配置

`ContextConfig` 新增 4 个字段：

| 字段                            |         默认值 | 作用                             |
|-------------------------------|------------:|--------------------------------|
| `self_compact_enabled`        |     `False` | 是否启用模型驱动的提前压缩                  |
| `self_compact_probe_interval` |         `1` | 每 N 个 reasoning iteration 检查一次 |
| `self_compact_min_iters`      |         `1` | 低于该 iteration 不检查              |
| `self_compact_rubric_prompt`  | 通用默认 prompt | 让模型判断 `COMPRESS` / `CONTINUE`  |

默认关闭是合理的：它不改变现有用户的固定阈值压缩行为。

### 9.2 结构化判定 schema

PR 增加了 `SELF_COMPACT_DECISION_SCHEMA`：

```python
{
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["COMPRESS", "CONTINUE"],
        },
        "reason": {
            "type": "string",
        },
    },
    "required": ["decision", "reason"],
    "additionalProperties": False,
}
```

也就是说，AgentScope 没有让模型自由输出文本再解析，而是走 `generate_structured_output`，降低判定解析失败概率。

### 9.3 默认 rubric prompt

PR 的默认 prompt 是通用型：

- 如果旧对话包含已经完成的工作、工具结果或中间推理，并且摘要能保留进展、降低干扰或上下文成本，则 `COMPRESS`；
- 如果近期细节仍需逐字保留、历史太少、压缩会丢失下一步所需信息，则 `CONTINUE`；
- 输出 `COMPRESS` 或 `CONTINUE`。

这和论文实现有明显差异：

| 维度        | 论文                    | AgentScope PR                  |
|-----------|-----------------------|--------------------------------|
| rubric 类型 | 数学/搜索任务特定             | 通用 rubric                      |
| 输出条件      | 多个显式条件，例如 C1/C2/C3/N1 | 单一自然语言判断                       |
| 证据要求      | 要求引用轨迹证据              | 默认 prompt 没有强制证据结构             |
| 触发单位      | token 或工具调用边界         | `cur_iter` reasoning iteration |
| backstop  | 搜索任务有 30% 强制 backstop | 保留原有 token threshold 机制        |

AgentScope PR 更像是把论文思想做成通用框架入口，而不是复刻论文实验 scaffold。

### 9.4 压缩流程接入点

原本 `_compress_context_impl` 只看 token 阈值：

```text
estimated_tokens >= trigger_ratio * context_size
```

PR 后逻辑变为：

```text
exceeds_threshold = estimated_tokens >= threshold

if not exceeds_threshold
   and self_compact_enabled
   and state.context exists:
       self_compact_requested = await _should_self_compact(...)

if not exceeds_threshold and not self_compact_requested:
    return

继续执行原有压缩流程
```

也就是说：

- 超过阈值：仍然按原逻辑压缩；
- 未超过阈值：如果 self-compact rubric 判定 `COMPRESS`，可以提前压缩；
- rubric 判定 `CONTINUE`：不压缩。

### 9.5 `_should_self_compact`

新增方法的逻辑：

```text
cur_iter = self.state.cur_iter or 0

if cur_iter < self_compact_min_iters:
    return False

if cur_iter % self_compact_probe_interval != 0:
    return False

if rubric_prompt is empty:
    return False

rubric_messages = messages + [UserMsg(content=rubric_prompt)]
res = model.generate_structured_output(
    messages=rubric_messages,
    structured_model=SELF_COMPACT_DECISION_SCHEMA,
)

return res.content["decision"].upper() == "COMPRESS"
```

这和论文一致的地方：

- 在推理中追加 rubric prompt；
- 用模型自己判断；
- 输出二元决策；
- 未超过固定 token 阈值时也可以提前压缩。

不完全一致的地方：

- 论文的 `CONTINUE` 会从真实轨迹中移除 probe；PR 里 `rubric_messages` 是新 list，不写回 `state.context`，等价于不污染轨迹；
- 论文强调 KV cache 复用；PR 层面只是调用模型 API，是否复用取决于底层模型服务；
- 论文的 summarizer prompt 是任务特定的；PR 复用 AgentScope 既有 summary schema 和压缩流程。

### 9.6 失败策略

PR 对失败处理比较谨慎。

rubric 失败：

```text
如果当前未超过 token 阈值，只是可选提前压缩失败，则记录 warning 并跳过压缩。
```

summary 失败：

```text
如果是 self_compact_requested 且未超过 token 阈值，则保留原始上下文。
```

这个设计很重要：self-compaction 是优化，不应因为可选判断失败中断正常回复。

但如果已经超过 token 阈值，仍走原有压缩异常处理，因为这时压缩是 overflow 防护，不是可选优化。

### 9.7 测试覆盖

PR 增加的测试覆盖了几个关键行为：

| 测试                                                         | 目的                      |
|------------------------------------------------------------|-------------------------|
| `test_self_compact_disabled_by_default`                    | 默认关闭，不额外调用 rubric       |
| `test_self_compact_can_trigger_early_compression`          | 未到 token 阈值也能提前压缩       |
| `test_self_compact_continue_skips_early_compression`       | 判定 `CONTINUE` 时跳过       |
| `test_self_compact_probe_interval`                         | 遵守 probe interval       |
| `test_self_compact_rubric_failure_skips_early_compression` | rubric 异常不影响正常上下文       |
| `test_self_compact_summary_failure_keeps_context`          | 可选提前压缩的 summary 失败时保留原文 |

这些测试主要验证控制流和容错，没有验证压缩质量。

---

## 10. 对 AgentScope PR 的技术评价

### 10.1 优点

1. **兼容现有行为**

   默认关闭，且超过 token 阈值时仍使用原压缩逻辑。

2. **实现面很小**

   没有引入新 memory subsystem，只是在现有 `_compress_context_impl` 前增加一个可选 early trigger。

3. **失败开放**

   低于阈值时的 self-compaction 是 best effort。rubric 或 summary 失败不会破坏会话。

4. **结构化输出**

   用 schema 约束 `COMPRESS` / `CONTINUE`，比正则解析自然语言稳。

5. **可配置**

   用户可以调整 probe interval、最小 iteration 和 rubric prompt。

### 10.2 局限

1. **默认 rubric 比论文弱**

   论文实验中 rubric 要求具体条件和轨迹证据，尤其搜索任务要求 C1/C2/C3/N1。PR 默认 prompt 是通用判断，没有强制引用证据，因此可能更容易过早或过晚压缩。

2. **没有任务特定 summarizer**

   论文里数学和搜索的 summarizer 目标不同。PR 复用通用上下文压缩流程，效果取决于 AgentScope 现有 summary schema
   是否足够表达任务状态。

3. **probe 粒度不同**

   论文数学任务按 round/token 边界，搜索任务按工具调用边界。PR 用 `cur_iter`，更通用，但未必等价于“closed unit”。

4. **没有显式 cost/KV cache 优化保证**

   论文的成本优势依赖 KV cache 复用。PR 在 Agent 层追加消息调用模型，但底层 provider 是否复用 cache 不由这段代码保证。

5. **没有质量评测**

   PR 测试验证功能，不验证在真实 benchmark 上是否提升 accuracy/cost。

### 10.3 更贴近论文的改进方向

如果后续要把 AgentScope 实现做得更接近论文，可以考虑：

1. **提供 rubric presets**

   例如：

    - `self_compact_rubric_type="general"`
    - `self_compact_rubric_type="math"`
    - `self_compact_rubric_type="search"`
    - `self_compact_rubric_type="coding"`

2. **要求 evidence-based structured output**

   不是只输出 `decision/reason`，而是让模型填：

   ```json
   {
     "closed_unit": {"answer": "Y", "evidence": "..."},
     "summarizable": {"answer": "Y", "facts": [...]},
     "progress": {"answer": "Y", "evidence": "..."},
     "stuck": {"answer": "N", "evidence": "..."},
     "decision": "COMPRESS"
   }
   ```

3. **区分压缩类型**

   数学任务可能需要 `preserve-answer`，搜索任务需要 `cite-able facts`，代码任务需要
   `files changed / commands run / failing tests / next edit`。

4. **把 probe 边界绑定到工具循环**

   对 ReAct Agent 来说，工具返回后、assistant 完成子分析后，通常比裸 `cur_iter` 更接近 closed unit。

5. **记录 self-compaction 事件**

   建议记录：

    - probe token count；
    - decision；
    - reason；
    - summary token count；
    - compressed message count；
    - 是否低于 threshold 提前压缩。

   这样才能分析实际触发分布和效果。

---

## 11. 总结

SELFCOMPACT 的关键贡献不是“摘要上下文”，而是把**压缩时机**从固定 token 阈值改成由模型根据轨迹状态判断，并用 rubric
把这个判断约束成可验证的条件。

论文实验说明：

- 固定压缩通常比不压缩好，但会在错误时机破坏关键状态；
- rubric-gated compaction 在数学和搜索任务上都优于固定间隔；
- rubric 是必要组件，去掉后收益基本消失；
- 成本下降来自摘要后后续 prompt 大幅缩短，而 probe 本身较便宜；
- 难题和长搜索任务收益最大。

AgentScope PR #1938 是一个轻量、兼容的工程落地版本：默认关闭，在未达到 token 阈值时允许模型通过通用 rubric
提前触发既有压缩流程。它抓住了论文最重要的方向，但没有完整复刻论文中的任务特定 rubric、evidence gate、summarizer prompt 和实验
cost 优化。因此可以把它理解为 **SELFCOMPACT-inspired early trigger**，而不是论文算法的严格实现。
