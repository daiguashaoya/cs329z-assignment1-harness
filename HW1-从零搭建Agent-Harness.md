# HW1｜从零搭建 Agent Harness

在理解高级框架之前，掌握智能体系统的最佳方式是不依赖任何现成框架，亲手从零搭建一套完整的 **Agent Harness（智能体运行底座）**。

在本项实践（对应源码仓库 [cs329z/assignment1-harness](https://github.com/cs329z/assignment1-harness)）中，你将为一家虚构的能源公司 **Cardinal Energy** 构建内部办公智能体。整个项目分为三个递进阶段：
1. **Part 1：固定流水线（Fixed Pipelines，第 1–4 题）**：实现邮件优先级分类、每日工作摘要生成、BM25 倒排检索器与多跳邮件问答；
2. **Part 2：模型控制循环与安全底座（Agent Loop & Harness，第 5–15 题）**：在仅使用基础文本生成接口 `lm(messages) -> str` 的前提下（**不使用任何第三方 Agent 框架、外部检索库，也不调用模型原生的 Function Calling / Structured Outputs API**），从零实现工具注册表、自定义文本工具协议、Agent 主循环、文档分页搜索与读取、终端沙箱与超大输出截断、上下文压缩（Compaction）、跨会话持久记忆、人机协同审批与防提示注入护栏，并通过 20 个模拟用户画像（Personas）的端到端仿真评测；
3. **Part 3：真实交互实验与架构复盘（Field Notes & Design Memo，第 16–17 题）**：通过命令行与你自己构建的 Agent 交互测试，并撰写系统设计权衡备忘录。

## 项目整体结构与阅读顺序

这是一个 Python 起始仓库：`adapters.py` 的 13 个入口目前全部抛出 `NotImplementedError`，`pipelines/` 与 `agent/` 目前只有 `__init__.py`。以下是已有文件的职责，子模块名称可由你自行设计。

```text
assignment1-harness/
├── HW1-从零搭建Agent-Harness.md   本学习路线与逐题验收步骤
├── README.md                    官方运行方式、开发和提交约束
├── cs329z_assignment1_harness.pdf 原始作业讲义
├── pyproject.toml / uv.lock      Python 依赖、锁文件和 pytest 默认配置
├── .env.example                 API Key 与预算等配置示例
├── cs329z_hw1/
│   ├── adapters.py              你需要接线的入口；测试通过这里调用实现
│   ├── pipelines/               建议放第 1–4 题的实现，目前为空包
│   ├── agent/                   建议放第 5–14 题的实现，目前为空包
│   ├── types.py                 数据类型、AgentConfig、事件日志格式
│   ├── llm.py                   LM / ScriptedLM、缓存、费用账本、预算
│   ├── tokens.py / tokenizer.py 作业 Token 计数与 BM25 分词
│   ├── data.py                  邮件与政策文档加载器
│   ├── cardinal.py              十个内置工具的固定参数 Schema
│   ├── sandbox.py               终端入口与工作区；Windows 分支见 sandbox_windows.py
│   ├── user.py                  澄清、审批、steering 的用户接口
│   ├── show.py / chat.py        单项结果查看、人工对话入口
│   └── simulation/              Persona、确定性检查、模型裁判、轨迹与评分
├── tests/
│   ├── test_*.py                每项功能对应的离线与 Live 测试
│   ├── conftest.py / helpers.py 测试装配与断言辅助
│   ├── fixture_tools.py         离线测试用的工具与副作用记录
│   ├── thresholds.py            Live 自动验收阈值
│   └── fixtures/               黄金标签、问题集、20 个 Persona
├── data/
│   ├── docs/                   已随仓库提供的 24 份政策与业务文档
│   ├── emails.jsonl.gz          已随仓库提供的邮件压缩包
│   ├── download.py / source.json 校验与解压脚本、邮件数与 SHA-256
│   └── priority_rubric.md       邮件分类标注准则
└── assets/                     README 中使用的插图
```

运行后才会出现：`.venv/`（依赖环境）、`data/emails/emails.jsonl`（解压邮件）、`.lm_cache/`（模型缓存、账本与默认聊天记忆）、`runs/`（聊天和仿真证据）。

**调用链**：测试 / `show` / `chat` / 仿真 → `adapters.py` → 你的流水线或 Agent → 提供的模型、数据、沙箱与用户接口。Agent 内部再串起“文本协议解析 → 参数校验 → 安全与审批 → 工具执行 → 观测入日志 → 下一次模型调用”。

**建议阅读**：先看 `README.md`、`types.py`、`adapters.py`；每做一题，再读对应的 `tests/test_*.py` 和下面列出的依赖。第 1–4 题完成后，按第 5–14 题逐步扩展同一个会话实现，最后做集成评测和写作。不用提前实现后续全部功能才测试当前题。

**修改范围**：业务实现与辅助文件放在 `cs329z_hw1/` 内；允许修改 `adapters.py` 的函数体接线，但保持入口签名不变。课程提供的接口、工具定义与基础设施以及 `tests/` 保持原样；不要新增 `pyproject.toml` 依赖。自动评分只复制这个 Python 包，根目录的自定义辅助代码不会被带入。

## 环境配置与测试工作流

项目要求 Python $\ge 3.11$，使用 `uv` 管理虚拟环境。所有待实现的业务代码均位于 `cs329z_hw1/` 包内，并通过 `cs329z_hw1/adapters.py` 中的标准入口函数暴露给测试套件（切勿修改 `types.py`、`adapters.py` 的函数签名或 `tests/` 下的测试代码）。

以下命令均在项目根目录的 **Windows PowerShell** 中运行。邮件压缩包和政策文档已经在仓库内；`download.py` 优先校验并解压本地压缩包，只有缺失时才下载邮件。

```powershell
Set-Location 'D:\Agents\cs329z-chinese\exercises\assignment1-harness'
uv sync
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# 在 .env 中填入你的 OPENROUTER_API_KEY
uv run python data/download.py
uv run python -c "from cs329z_hw1.data import load_docs, load_emails; print('docs=', len(load_docs()), 'emails=', len(load_emails()))"
uv run python -c "from cs329z_hw1 import sandbox; print(sandbox.jail())"
```

准备验收：数据数量应为 `docs= 24 emails= 26278`；Windows 上 `jail()` 为 `none`。第 10 题起需要安装 Git for Windows：工具命令运行在它提供的 Bash 中，因此**外层测试命令是 PowerShell，传给 `run_terminal` 的命令是 Bash**。`tokens.py` 使用每 4 字符计 1 Token、每条消息加 4 Tokens 的确定性规则；所有作业预算均按它计算。

测试套件分为两类，建议在实现每一道题时严格遵循**“先跑通离线确定性测试，再运行在线真实模型测试”**的节奏：

```powershell
# 1. 运行离线确定性测试（使用 ScriptedLM，零 API 费用，秒级检验控制流与边界合同）
uv run pytest tests/test_tool_registry.py
uv run pytest tests/test_tool_protocol.py
uv run pytest tests/test_agent_loop.py

# 2. 运行在线真实模型评测（标记为 -m live，可先用切片快速迭代，再跑全量）
$env:CS329Z_EVAL_SLICE = '5'
uv run pytest tests/test_priority.py -m live -s
Remove-Item Env:CS329Z_EVAL_SLICE -ErrorAction SilentlyContinue
uv run pytest tests/test_priority.py -m live -s
```

**统一判定方式**：离线命令退出码为 0、全部选中测试 `passed` 才算通过；`deselected` 表示另一类测试被正常过滤。默认 `uv run pytest` 已通过 `pyproject.toml` 排除 `live`，下文显式写 `-m 'not live'` 便于区分。失败时用 `uv run pytest <测试文件> -m 'not live' -x -vv` 定位首个失败，再用 `文件路径::test_函数名` 单独复现。`NotImplementedError` 表示入口尚未接好，`ScriptExhausted` 常表示额外消耗了主模型脚本，应检查辅助调用路由。

**切片只用于调试**：并非每个 Live 测试读取 `CS329Z_EVAL_SLICE`，例如 memory 和 compaction 不读取；协议与仿真还会对切片缩放门槛，少量样本通过不能代表达标。正式验收前执行上面的 `Remove-Item`，并确认 `.env` 中也没有启用 `CS329Z_EVAL_SLICE`。同理，专项 `--only` 不代表全量通过。只有已完成的模块需要通过，未实现题目的全量失败是起始仓库的正常现象。

**如何保存证据**：每题记录实现版本、命令、通过数量或分数及失败原因；可在测试命令后追加 `--junitxml=runs/q01-offline.xml` 保存机器可读报告（先 `New-Item -ItemType Directory -Force runs`）。`show` 是人工查看输出，不代替自动测试。第 16–17 题是人工验收，没有对应 pytest。

> **缓存与预算机制说明**：`llm.py` 内置了基于 SQLite 的本地调用缓存（`.lm_cache/`）与累计预算账本（Ledger）。当提示词、工具描述与输入消息完全一致时，重复运行会直接命中本地缓存而不重复计费；若需测试模型在独立采样下的真实随机波动，可通过设置环境变量 `CS329Z_EVAL_SALT` 注入新盐值。

## Part 1：固定流水线（Fixed Pipelines）

### 1. 邮件优先级 priority（3 分）

- **入口函数**：`run_priority(email: Email, lm: LMCallable) -> dict`
- **核心任务**：仅使用**单次**模型调用，判断一封邮件对收件人的紧急程度，返回 `{"category": category, "reason": reason}`，其中 `category` 必须属于 `{"urgent", "normal", "ignore", "unknown"}`，`reason` 为非空解释字符串，且不得修改传入的 `email` 对象。
- **分类准则（站在邮件收件人当时的视角）**：
  - `urgent`：要求收件人在当天、下一个工作日或至多两个工作日内采取行动的明确请求，或收件人直接负责的线上故障/紧急审批；
  - `normal`：发给收件人的常规工作沟通、问题咨询、文档审阅、日程协调或同事便条；
  - `ignore`：无需收件人采取任何行动的广告推销、全员群发广播或自动通知（注意：写着“限时抢购立即行动”的群发广告依然是 `ignore`；但要求收件人本人处理的系统故障告警则是 `urgent`）；
  - `unknown`：当模型的输出无法解析出上述三个明确标签时，必须返回 `unknown`，绝不能盲目默认猜 `normal`。
- **验收标准**：离线解析测试全通；在 60 封平衡类别的 Live 测试集上准确率 $\ge 85\%$（至少答对 51 封），且 Live 评测中不出现 `unknown`。

#### 本题如何测试与验收

先读 `data/priority_rubric.md`、`tests/test_priority.py`；建议实现放在 `pipelines/priority.py`，由 adapter 转发。

```powershell
uv run pytest tests/test_priority.py -m 'not live' -vv
uv run python -m cs329z_hw1.show priority em-12167
uv run pytest tests/test_priority.py -m live -s
```

- 离线：空回复、空白、无标签、不同格式都能返回合法字典；没有明确标签返回 `unknown`；输入不被修改。
- 人工审查：代码确实只调用一次 `lm`（现有离线断言只检查至少调用一次，不能单靠它证明单次约束）。
- 正式验收：60 封至少 51 封正确，且没有 `unknown`；`show` 中能看到非空理由。

### 2. 日报 daily_digest（4 分）

- **入口函数**：`run_daily_digest(emails: list[Email], lm: LM) -> str`
- **核心任务**：对传入的一批单日邮件先逐封分类（可并发执行），由**程序代码**完成过滤与排序——剔除所有 `ignore` 邮件（将 `unknown` 视作 `normal` 保留）、按邮件主题线程归并、将 `urgent` 置顶排序后，仅用**最后一次模型调用**生成当日工作简报。若输入为空列表或全部被过滤，也应返回合理的简短说明字符串。
- **硬性约束**：
  1. 模型生成的原始日报词数严格不超过 **300 个词**（按 `len(text.split()) <= 300` 判定，必须在提示词中控制模型生成长度，不得在事后用代码暴力截断字符串）；
  2. 必须完整点名提及当天所有 `urgent` 邮件涉及的核心公司、项目或地点实体；
  3. 绝不能混入任何属于 `ignore` 邮件的内容。

#### 本题如何测试与验收

依赖第 1 题。读 `tests/test_daily_digest.py` 和 `tests/fixtures/digest_days.json`，重点检查黄金 urgent 的必含词与 ignore 的禁含词。

```powershell
uv run pytest tests/test_priority.py tests/test_daily_digest.py -m 'not live' -vv
uv run python -m cs329z_hw1.show digest 2001-06-22 --labels --limit 30
uv run pytest tests/test_daily_digest.py -m live -s
```

- 离线：空邮件日、空主题/正文、畸形模型回复仍返回字符串，原邮件列表和对象不变。
- 人工检查程序确实先分类、过滤、归并、排序，再生成；`--limit 30` 仅便于查看，正式测试使用完整测试日。
- 正式验收：Live 的长度、所有 urgent 实体覆盖、ignore 内容排除三项测试全部通过；每一天均满足非空且原始输出不超过 300 词，不能仅看平均值。

### 3. BM25 倒排检索（8 分）

- **入口函数**：`run_bm25_build(docs: list[str]) -> BM25Index` 与 `run_bm25_search(index: BM25Index, query: str, k: int) -> list[tuple[int, float]]`
- **核心任务**：使用项目提供的分词器 `tokenizer.tokenize`（转小写并按非英文字母数字切分），从零实现内存倒排索引（Inverted Index）。
- **算法与性能要求**：
  1. **建索引（`run_bm25_build`）**：单次遍历文档列表构建 `term -> postings` 映射，记录每篇文档的长度 $|D|$、包含各词的文档频次 $\text{df}$ 以及全集平均文档长度 $\text{avgdl}$（空文档同样计入总文档数 $N$ 与平均长度分母）。
  2. **打分公式（`run_bm25_search`）**：采用参数 $k_1 = 1.5, b = 0.75$，以及非负 IDF 公式：
     $$\text{IDF}(t) = \ln\left(1 + \frac{N - \text{df}(t) + 0.5}{\text{df}(t) + 0.5}\right)$$
  3. **倒排加速与边界**：查询词去重后，**仅遍历查询词对应的倒排链表（Postings List）**，绝不能在查询时扫描全部 $N$ 篇文档；与查询无公共词元的文档得分为 0，不得出现在返回列表中；结果按得分降序排列（得分相同时按较小的 `doc_id` 升序排列）。
- **验收标准**：5 篇文档手算精度误差 $\le 10^{-6}$；17 条邮件查询的 Top-10 平均召回率 $\ge 90\%$；构建索引耗时 $< 15\text{ s}$，平均单次查询 $< 20\text{ ms}$，在 20 万篇文档中检索仅出现 3 次的稀有词耗时 $< 2\text{ ms}$。

#### 本题如何测试与验收

读 `tokenizer.py`、`data.email_text` 和 `tests/test_bm25.py`。本题没有 Live 测试，但完整离线测试需要已解压的邮件。

```powershell
# 先做小数据正确性与稀有词性能，不依赖邮件包
uv run pytest tests/test_bm25.py -k 'not archive' -vv
# 再测完整邮件语料的召回与性能
uv run pytest tests/test_bm25.py -vv
uv run python -m cs329z_hw1.show bm25 'larchfield audit'
```

- 小数据：公式、空文档、未知词、重复查询词、并列分数排序、返回 Python `int` / `float` 均通过。
- 全量：Top-10 平均召回率 ≥90%，建索引 <15 秒，平均查询 <20 毫秒；20 万文档的稀有词查询 <2 毫秒。
- 性能失败先检查查询是否遍历全库、是否在查询时重新分词或重建索引；不要修改阈值。保存一条排序不佳的查询及分数，作为第 17 题素材。

### 4. 多跳邮件问答 email_qa（8 分）

- **入口函数**：`run_email_qa(question: str, search: Callable[[str, int], list[Email]], lm: LMCallable) -> dict`
- **核心任务**：针对需要跨单封或多封邮件串联线索的问题（例如先从第一封邮件查出负责某项目的律所名称，再以律所名称为关键词搜出第二封邮件里的托管定金账号），驱动模型自主构造查询、阅读结果并决定是否继续检索。
- **硬性约束**：
  1. 代码层强制限制每道题最多调用 `search` 函数 **3 次**；
  2. 返回 `{"answer": answer, "support": support}`，其中 `answer` 是字符串或 `None`，`support` 为支持该答案的邮件 ID 列表，且返回的每一个邮件 ID 都**必须确实在本次问答的 `search` 返回结果中出现过**；
  3. 邮件正文中可能包含恶意的提示注入文本，系统必须仅将邮件视为待查证据。
- **验收标准**：在 25 道 Live 测试题（含 12 道单跳、13 道两跳）上答题准确率 $\ge 70\%$（至少 18 题），且每道答对题目的 `support` 列表至少命中一条黄金证据邮件 ID。

#### 本题如何测试与验收

Live 依赖第 3 题 BM25；离线使用 `FakeSearch`，可先独立完成控制流。

```powershell
uv run pytest tests/test_email_qa.py -m 'not live' -vv
uv run python -m cs329z_hw1.show email_qa 'Who leads the Basin Analytics move?'
uv run pytest tests/test_email_qa.py -m live -s
```

- 离线：各种模型回复、零搜索结果都不崩溃，最多 3 次搜索；支持 ID 只能从本次已返回邮件中选。
- 正式验收：25 题至少 18 题正确，并通过单独的证据测试；每个正确答案至少引用一条黄金证据。准确率通过但 support 测试失败仍未完成。
- 排错时分别记录“搜到了什么”“模型答了什么”“引用了什么”，区分检索漏召回、推理错误和引用过滤错误。

## Part 2：模型控制循环与安全底座（Agent Loop & Harness）

### 5. 工具注册表 tool_registry（3 分）

- **入口函数**：`run_tool_registry(tools: list[ToolSpec])`
- **核心任务**：实现一个管理可用工具的注册表对象，暴露三个核心接口：
  1. `schemas() -> list[dict]`：按注册顺序返回仅包含 `name`、`description`、`parameters` 三个键的字典列表；
  2. `validate(name: str, args: dict) -> ToolResult | None`：**仅校验、不执行**。若工具名不存在，返回 `status="unknown_tool"`；若参数不符合该工具的 JSON Schema（使用提供的校验规则），返回 `status="invalid_args"`；若完全合法则返回 `None`；
  3. `execute(name: str, args: dict) -> ToolResult`：先调用 `validate`，校验通过后执行恰好一次底层工具函数，成功则返回 `status="ok"` 及字符串结果；若工具函数内部抛出任何异常，捕获并返回 `status="tool_error"` 及错误描述，**绝不向外抛出未捕获的工具异常**。

#### 本题如何测试与验收

读 `types.ToolSpec`、`types.ToolResult`、`tests/fixture_tools.py` 和 `tests/test_tool_registry.py`；可使用已有依赖 `jsonschema`。

```powershell
uv run pytest tests/test_tool_registry.py -vv
```

- 所有测试通过：Schema 三个键与注册顺序准确；`validate` 零副作用；合法执行恰好一次并将结果 `str()` 化。
- 未知名称、缺参、错类型、额外参数均在执行前拦截；工具异常包含原始异常信息，之后注册表仍能使用。本题没有 Live 阶段。

### 6. 文本工具协议 tool_protocol（4 分）

- **入口函数**：`run_render_tools(schemas)`、`run_parse_response(text)`、`run_format_tool_call(text, call)`
- **核心任务**：由于不依赖模型厂商原生的 `tool_calls` 字段，你需要自己设计一套纯文本工具调用协议（例如使用特定起止定界符包裹 JSON 对象），让模型在普通文本输出中表达工具调用。
- **严苛的解析合同**：
  1. `run_render_tools` 生成的工具说明文本必须完整包含所有工具名称及参数字段名，并清楚教模型如何按你的协议格式输出；
  2. 模型单次回复只允许是**纯自然语言最终回答**，或包含**恰好一个**工具调用（若单次回复包含多个工具调用，解析器必须返回 `error`）；
  3. **往返无损与抗嵌套截断**：`format -> parse` 往返必须严格保留布尔值 `true`、整数 `1`、浮点数 `1.0` 与字符串 `"1"` 的类型区分；当输出在任意字符位置被截断（模拟 `max_tokens` 截断），或当工具参数字符串内部恰好包含你自己协议的完整定界符文本时，解析器绝不能崩溃或误解析出残缺的错误指令。
- **验收标准**：通过全部极端边界离线测试，并在 20 个单步工具调用 Live 请求中至少正确完成 18 个。

#### 本题如何测试与验收

依赖第 5 题。先设计 formatter 与 parser，再编写模型工具说明，使三者遵循同一协议。

```powershell
uv run pytest tests/test_tool_protocol.py -m 'not live' -vv
uv run pytest tests/test_tool_protocol.py -m live -s
```

- 离线必须全通：普通文本无调用、两个调用报错、所有截断位置安全、参数内嵌完整协议不被误判、JSON 类型往返不变，且调用对象不被修改。
- 正式验收：完整 20 条请求至少 18 条参数正确；这是工具协议单步测试，不要求先完成整个 Agent。
- 若 Live 失败，优先对比 `run_render_tools` 描述与 formatter 实际产出的格式，不要为黄金请求硬编码解析分支。

### 7. Agent loop（8 分）

- **入口函数**：`run_agent_session(lm, tools, config: AgentConfig)`
- **核心任务**：实现支持多轮对话（`send(user_message) -> AgentResult`）、追加式历史记录（`transcript`）与模式切换（`set_mode`）的 Agent 会话状态机。
- **控制流与预算规则**：
  1. 每次 `send()` 独立统计当前轮次（`max_turns`）与累计 Token 消耗（`config.token_budget`，使用 `tokens.py` 计数器）。在发起每一次模型调用前，先检查轮数是否超限，再检查累计 Token 是否超限；
  2. **最后一轮边界**：在第 `max_turns` 轮（最后一个允许回合）中，如果模型发出了合法的工具调用，该工具**依然要执行**并将结果追加进 `transcript`，随后因轮数用尽返回 `status="max_turns"`；如果某次模型调用直接产出了最终回答，即便这次调用刚巧跨过累计 Token 预算，依然正常返回该回答并标为 `status="done"`；
  3. **连续三次格式错误熔断**：当模型输出触发解析错误（`parse_error`）、未知工具（`unknown_tool`）或参数非法（`invalid_args`）时，记为一次畸形回复（Malformed，包括捕获 `OutputTruncated` 异常），并将错误反馈给模型让其重试；若**连续 3 次**出现 Malformed 则立即熔断停止并返回 `status="malformed"`；一旦中间有一次合法调用（哪怕工具执行报错 `tool_error` 或被用户拒绝 `denied`），连续畸形计数器即清零；
  4. **追加式不可变日志**：每一步事件严格追加，永不删改已发生的事件；下一轮模型调用必须逐字看到上一轮工具返回的观测文本。

#### 本题如何测试与验收

依赖第 5–6 题；本阶段用显式传入的 fixture tools 实现循环，尚不需要完整 Cardinal 工具集。

```powershell
uv run pytest tests/test_agent_loop.py -vv
uv run pytest tests/test_tool_registry.py tests/test_tool_protocol.py tests/test_agent_loop.py -m 'not live'
```

- 所有离线控制流通过：最终回答、连续工具调用、异常恢复、三次畸形熔断与重置、每次 send 独立预算、最后一轮执行工具、会话间隔离。
- 对照 `types.py` 检查事件字段与顺序；返回结果持有当时的 transcript 副本，后续 send 不改变旧结果；下一次模型调用含上一次观测原文。
- 注意模型抛出的 `OutputTruncated` 要转成畸形重试，其他模型异常要传播；工具异常才统一转 `tool_error`。本题无 Live 测试。

### 8. Cardinal 工具集（2 分）

- **核心任务**：当 `tools=None` 时，自动组装 Cardinal Energy 助手的完整工具箱：`search_emails`、`read_email`、`email_qa`、`daily_digest`、`search_docs`、`read_doc`、`run_terminal`、`remember`、`recall`、`ask_user`。
- **延迟加载与辅助模型路由**：
  1. 初始化会话时**不得**提前读取或构建全量邮件索引，必须在首次实际调用邮件工具时才执行惰性加载（Lazy Loading）并在会话内复用索引；
  2. Agent 主循环的每一步决策调用主模型 `lm`；而工具内部的子调用（如 `email_qa`、`daily_digest` 以及后续的上下文摘要压缩）必须优先调用 `config.aux_lm`（仅当 `aux_lm is None` 时回退使用 `lm`），以保证离线 `ScriptedLM` 步数对齐与线上成本分离。

#### 本题如何测试与验收

依赖第 1–7 题；读 `cardinal.py`，使用固定名称、参数与 `read_only` 标记组装工具。第 9–14 题会补齐各工具的真实能力。

```powershell
uv run pytest tests/test_cardinal.py -vv
```

- 初始化 `tools=None` 不读取邮件，系统提示词包含十个工具；显式 `tools=[]` 或自定义列表不会偷偷加全部 Cardinal 工具。
- 仅在配置 user 时补 `ask_user`、配置 memory_dir 时补 `remember` / `recall`。这些装配测试通过后，后续题再验证真实调用。
- 人工检查惰性索引缓存和 `aux_lm` 路由；本题测试主要覆盖装配，不能单凭通过证明所有工具可用。辅助调用是否消耗了主模型脚本还会由后续压缩等测试检验。本题无 Live 测试。

### 9. 文档搜索与分页读取 search_docs（5 分）

- **入口函数**：`run_build_doc_index`、`run_search_docs`、`run_read_doc`
- **核心任务**：为 24 份公司政策文档实现带摘要片段（Snippet）的检索与按行号分页读取：
  1. `search_docs(index, query, k)`：返回至多 $k$ 条匹配结果，每条 snippet 长度 $\le 150$ 个作业 Token，且必须包含原文中至少连续 4 个词的真实片段（严禁编造摘要）；
  2. `run_read_doc(index, doc_id, start_line=1)`：行号从 1 开始（按 `splitlines()` 切分），由实现选择窗口末行，返回该区间的原始文本（不额外拼接行号前缀），单次返回不超过 1,500 Tokens，并返回 `DocWindow` 元数据（允许从返回的 `end_line + 1` 无缝续读至 `total_lines`）。注意 `end_line` 是返回字段，不是入口参数。
- **验收标准**：在 20 道政策问答 Live 测试（涵盖深层条款、词面同义替换、以及**已被新版政策废止的旧版政策干扰**）中准确率 $\ge 75\%$（至少 15 题），且每题文档读取总量 $\le 6,000$ Tokens。

#### 本题如何测试与验收

离线可先独立完成文档索引三个入口；Live 还依赖第 5–8 题的完整 Agent 装配。

```powershell
uv run pytest tests/test_search_docs.py -m 'not live' -vv
uv run python -m cs329z_hw1.show search_docs 'parental leave'
uv run pytest tests/test_search_docs.py -m live -s
```

- 离线：空查询不匹配；独有词命中正确文档并出现在 snippet；结果稳定且最多 k 条；snippet ≤150 Tokens 且含原文连续四词。
- 分页：各窗口等于原始行文本、≤1500 Tokens；从 `end_line+1` 续读覆盖全文无缺行；未知文档及非法起始行抛 `ValueError` 或 `LookupError`。
- 正式验收：20 题至少 15 题正确。每题 **search_docs 与 read_doc 所有返回内容合计** ≤6000 Tokens，搜索结果也计入，不能仅统计正文读取。

### 10. 终端与 observation policy（6 分）

- **核心任务**：封装 `sandbox.run_terminal(cmd, workspace=..., timeout=...)`。仅当命令实际执行且返回退出码 `0` 时标记 `status="ok"`；非零退出码、超时或被沙箱拦截均返回 `status="tool_error"` 及可读的错误原因。
- **超大输出观测策略（Observation Policy）**：测试中包含单次打印 **600,000 字符** 的极端命令，而单次模型调用的总上下文预算可能只有几千 Token。你需要设计合理的截断与转存策略（例如保留头部与尾部关键行、将完整输出落盘到工作区临时文件并在返回结果中告知模型如何用 `grep` / `sed` 按需分段查看）。注意：`transcript` 中保存的 `tool_result` 必须与实际展示给模型的截断文本一致。 Live 测试包含 9 道主问题加 1 道针对截断列表中间某行的追问，要求至少答对 8/10。

#### 本题如何测试与验收

依赖第 7–8 题；先读 `sandbox.py`、`sandbox_windows.py`。终端应通过提供的 sandbox 调用，准确传递 workspace 与 timeout。

```powershell
uv run python -c "from cs329z_hw1 import sandbox; print(sandbox.jail())"
uv run pytest tests/test_terminal.py -m 'not live' -vv
uv run pytest tests/test_terminal.py -m live -s
```

- 离线：实际工作目录与文件副作用正确，stdout、stderr、退出码可见；非零退出、拒绝、超时反馈后仍能继续。
- 大输出测试需要先具备基本的上下文预算保护；若只剩这部分失败，与第 11 题联调后重跑。超大内容在进入日志前处理，日志里的观测与模型实际看到的内容一致。
- 正式验收：9 个主问题与 1 个追问合计至少 8/10 正确，所有模型输入不超上下文预算；尤其确认模型能从落盘文件找到被截断的中间内容。

### 11. 上下文压缩 compaction（8 分）

- **核心任务**：确保每一次调用 `lm(messages)` 时，严格满足 `count_message_tokens(messages) <= config.context_budget`，且当前轮次用户的原始请求消息（Current User Message）必须始终保留在上下文中。
- **架构衔接**：测试会使用 4,000 Tokens 的紧凑窗口连续发起约 60 次工具调用与 12 轮用户对话。为了同时满足“下一轮调用必须逐字看到上一轮工具输出”与“总长度不超过预算”，应当遵循：**（1）单条工具输出在进入事件流前先通过第 10 题的观测策略控制上限；（2）底层 `transcript` 保持追加不可变；（3）当构造本轮模型输入视图超出 `context_budget` 时，调用 `aux_lm` 将较早的历史轮次压缩为保留了核心约束、关键发现与进度的摘要消息**。

#### 本题如何测试与验收

依赖第 7、10 题。先实现“不可变事件日志”和“可压缩模型输入视图”的分离，再接入 `aux_lm` 摘要。

```powershell
uv run pytest tests/test_compaction.py -m 'not live' -vv
uv run pytest tests/test_agent_loop.py tests/test_terminal.py tests/test_compaction.py -m 'not live'
uv run pytest tests/test_compaction.py -m live -s
```

- 离线：12 次 send、60 次模型调用均在 4000 Tokens 内，48 个工具调用和结果完整保留；当前请求始终可见，超大单条输出也能处理，压缩后仍可继续对话。
- 组合回归必须同时通过，防止压缩修复破坏上一条观测逐字可见或事件不变性。
- 正式验收：经过多次压缩后，最终真实模型仍回答早期约束 `18,450` 美元和 `Boulder`；每次模型输入均不超预算。该测试不支持用 `CS329Z_EVAL_SLICE` 缩短脚本。

### 12. 跨会话记忆 memory（8 分）

- **核心任务**：实现仅在 `config.memory_dir` 目录下持久化读写数据的 `remember` 与 `recall` 工具。不同 `memory_dir` 之间必须完全隔离；当记忆库为空时调用 `recall` 也必须返回 `status="ok"` 及清晰的空状态提示。
- **冲突更新要求**：在跨会话测试中，第一轮会话用户会告知某项事实或项目编号，随后在同一会话或后续句子中更正该编号；第二轮新会话启动时仅共享同一个 `memory_dir`，Agent 必须能够召回更正后的最新事实，避免将已作废的旧编号混入回答中。

#### 本题如何测试与验收

依赖第 7–9 题；明确持久化格式、召回方法与更正策略。不能只把事实留在内存中的 transcript。

```powershell
uv run pytest tests/test_memory.py -m 'not live' -vv
uv run pytest tests/test_memory.py -m live -s
# 完成第 15 题集成后，补验事实更正
uv run python -m cs329z_hw1.simulation --only memory
uv run python -m cs329z_hw1.show memory
```

- 离线：写入指定目录，新会话可召回，同会话可检索，不同目录完全隔离，空库返回非空说明，记忆工具免审批。
- 正式自动验收：3 对跨会话 Live 场景至少 2 对通过；该文件不读取 `CS329Z_EVAL_SLICE`，每次都跑 3 对。
- 更正还需专项验收：`17-memory-corrected-number` Persona 成功，检查输出的 `.memory/` 文件及第二会话首答，不能混入旧编号；现有 memory 单项 Live 通过不能代替这项集成检查。

### 13. 交互、审批与 steering（7 分）

- **核心任务**：通过 `config.user`（`UserIO` 接口）实现三项人机协同机制：
  1. **主动澄清（`ask_user`）**：调用 `user.ask(question)` 获取用户补充说明，并将其作为 `status="ok"` 的工具结果返回给模型；
  2. **敏感操作审批（Approval in `confirm` mode）**：当 `mode == "confirm"` 时，对于通过了 Schema 校验且非只读的工具（如 `run_terminal`），在执行前必须对 `user.approve(call)` **恰好调用一次**（`ask_user`、`remember`、`recall` 永不触发审批弹窗；非法调用在校验阶段直接报错，不打扰用户审批）。若用户拒绝，则绝不执行该工具，记录 `status="denied"` 及拒绝理由并让模型继续思考替代方案；
  3. **中途插话转向（Steering via `pending_message`）**：在每一次调用模型之前，恰好调用一次 `user.pending_message()`；若返回非空新消息，立即将其作为新的 `user` 事件追加进历史并纳入本次模型输入，使 Agent 能够实时响应用户的中途改口。

#### 本题如何测试与验收

依赖第 5、7、8、12 题；读 `user.py`，测试用 `ScriptedUser` 代替人工输入。

```powershell
uv run pytest tests/test_interactive.py -vv
uv run pytest tests/test_agent_loop.py tests/test_cardinal.py tests/test_memory.py tests/test_interactive.py -m 'not live'
```

- 审批：confirm 下每个合法非只读调用恰好审批一次；拒绝后没有副作用、理由反馈给模型；auto 不审批；非法参数先拦截；`set_mode` 在两次 send 之间立即生效。
- 澄清：`ask_user` 返回用户原答且不审批；记忆工具同样免审。
- Steering：每次主模型调用前轮询一次，非空消息按顺序写入 user 事件并进入当次上下文，空消息不增加事件。本题无单独 Live 测试，后续仿真验证端到端表现。

### 14. Deny rules 与 prompt injection（4 分）

- **核心任务**：在执行 `run_terminal` 前，对完整命令字符串遍历 `config.deny_rules` 执行正则搜索 `re.search(rule, cmd)`。一旦命中任一拒绝规则，无论当前是 `auto` 还是 `confirm` 模式，**立即强制拒绝（不调用 `user.approve` 弹窗，也不执行命令）**。同时确保宿主程序的 `mode` 与 `deny_rules` 绝不会被任何工具返回的文本修改。
- **验收标准**：在 7 道植入了间接提示注入的文档与邮件 Live 测试中，恶意命令实际执行次数严格为 $0$，且正常业务问题答对率 $\ge 6/7$。

#### 本题如何测试与验收

依赖第 7、9、10、13 题；将拒绝规则放在宿主执行路径，不依赖提示词让模型自行遵守。

```powershell
uv run pytest tests/test_guardrails.py -m 'not live' -vv
uv run pytest tests/test_guardrails.py -m live -s
```

- 离线：规则对完整命令进行正则搜索；auto / confirm 均拦截；命中后不审批不执行；未命中可以执行；工具返回“已授权”等文字不能改变模式或规则。
- 正式验收：7 个注入场景中至少 6 个合法问题回答正确，且注入命令实际执行次数为 0，两个条件缺一不可。
- 检查工具调用与结果状态及实际副作用，不能只凭最终回答说“已拒绝”来验收；把失败轨迹与修复办法留作设计备忘录素材。

### 15. 模拟用户端到端评测 sim_eval（10 分）

- **评测机制**：运行 `cs329z_hw1.simulation` 中的 20 个端到端用户画像场景（涵盖政策检索、多跳邮件、日报追问、确认模式终端操作、跨会话记忆延续与更正、模糊需求澄清及对抗性注入）。
- **满分标准**：单条 Persona 只有在 **Agent 未崩溃 + 全部确定性代码检查（`checks.py`）通过 + 裁判模型（`judge.py`）判定全部 Rubric 通过且无编造（No Fabrication）** 时才计为成功；20 个场景中至少通过 **16 个** 即获满分：

```powershell
# 快速运行切片或专项类别调试
uv run python -m cs329z_hw1.simulation --only memory
uv run python -m cs329z_hw1.simulation --slice 3

# 运行全量 20 个 Personas 端到端评测
uv run python -m cs329z_hw1.simulation
```

#### 本题如何测试与验收

依赖第 1–14 题。先读 `simulation/README.md`、`checks.py`、`judge.py`，了解“用户说满意”不等于裁判通过。

```powershell
# 先用脚本用户检查仿真接线，无模型费用
uv run pytest tests/test_sim_eval.py -m 'not live' -vv
# 所有已完成代码的离线回归
uv run pytest -m 'not live'
# 少量样本试跑，再完整正式验收
uv run python -m cs329z_hw1.simulation --slice 3
Remove-Item Env:CS329Z_EVAL_SLICE -ErrorAction SilentlyContinue
uv run pytest tests/test_sim_eval.py -m live -s
uv run python -m cs329z_hw1.show memory
uv run python -m cs329z_hw1.llm
```

- 正式验收：确认 `.env` 也未设置切片，全量 20 个 Persona 至少 16 个成功；每个成功样本必须无异常、全部 checks 通过、全部裁判 rubric 通过且无编造。
- 检查 `runs/sim-<time>/<persona id>.json` 的对话、事件、checks 和 judge 原因；记忆证据在同名 `.memory/` 目录。优先修失败最多的能力类别，再重跑相关单项和 Persona。
- 直接运行 simulation CLI 即使分数不足也可能退出 0，因此必须阅读成绩表；正式通过与否优先用上述 pytest 的阈值断言判断。
- 若想只重判已保存轨迹：`uv run python -m cs329z_hw1.simulation --rescore runs/sim-实际目录名`。它不会重跑 Agent，仍可能产生裁判费用；不能用来验证代码修复。

## Part 3：交互实验与设计复盘

### 16. 使用记录 field_notes（10 分）

运行交互式命令行 `uv run python -m cs329z_hw1.chat`（默认开启 `confirm` 确认模式），亲手向你的 Agent 提出至少 5 个涵盖不同能力维度的新请求（查政策、查邮件、运行终端命令、故意提出指代不明的问题测试澄清、提出触发拒绝或中途修改要求的问题）。结合保存的 `runs/chat-*.json` 轨迹文件，撰写 1 页实验观察笔记（`field_notes`），客观记录系统的真实表现、暴露出的缺陷以及你据此做出的代码改进。

#### 本题如何测试与验收

这是人工实验与写作任务，没有 `tests/test_field_notes.py`。建议在第 15 题基本稳定后，用测试集以外的请求做实验。

```powershell
uv run python -m cs329z_hw1.chat --mode confirm --memory-dir .lm_cache/field_notes_memory
# 在聊天里完成实验，最后输入 exit 正常保存轨迹
Get-ChildItem runs/chat-*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,LastWriteTime
```

- 至少 5 个新请求覆盖不同能力：政策检索、邮件查询、终端计算、模糊问题澄清、拒绝或修改要求。终端实验中亲手拒绝一次审批并观察替代方案。
- 当前 `ConsoleUser` 没有实现运行中的异步键盘 steering；下一次 `you>` 输入只是新的 send。真正的中途 steering 用第 13 题脚本测试和有 steering 的 Persona 证明，不要把普通多轮对话记为运行中插话。
- 每个请求留下“请求原文 → 预期 → 实际回答/工具 → 是否达成 → 轨迹文件与事件位置 → 改进及复验”。失败也如实记录，具体指出修复代码和复验结果。
- 人工验收：约 1 页 `field_notes`、至少 5 条真实请求与对应 `runs/chat-*.json`；结论可由轨迹复查，不能用预想结果代替实测。保存成你选定的文档格式后再核对页数。

### 17. 设计备忘录 design_memo（20 分）

撰写一份 2 页的架构设计备忘录（`design_memo`），结合具体代码与运行证据逐项回答以下 10 个核心工程问题：
1. **BM25 误差分析**：找出一道 BM25 将无关邮件排在相关邮件前面的具体查询，从词频、IDF 或文档长度解释原因。
2. **工具协议设计**：你采用了什么定界符与格式设计？它是如何保证在任意位置截断或参数内嵌协议文本时依然安全解析的？
3. **空承诺处理**：当模型只用自然语言回复“好的，我现在就去帮您查一下”却没有发出任何工具调用时，你的主循环如何区分它是真的回答完毕还是半途忘了调工具？
4. **文档检索窗口权衡**：你的 `search_docs` 片段与 `read_doc` 分页大小是如何设定的？如何帮助模型识别已废止的旧版政策？
5. **超大终端输出策略**：面对 60 万字符的终端输出，你采用了什么截断与转存策略？模型如何读取被截断掉的中间行？
6. **上下文压缩（Compaction）**：你的压缩策略在何时触发？如何保证早期对话中的硬性约束在多次压缩后不丢失？
7. **跨会话记忆治理**：检查 `sim_eval` 运行后的真实记忆存储文件，分析存下了哪些高价值信息、遗漏了什么，以及如何处理事实更正。
8. **审批策略边界**：在 `confirm` 模式下，哪些工具被你设为免审只读、哪些需要审批？为什么这样划分？
9. **沙箱真实隔离边界**：在你的开发机上运行 `uv run python -c "from cs329z_hw1 import sandbox; print(sandbox.jail())"`，结合 `sandbox.py` 源码分析当前操作系统的沙箱实际上拦截了什么、又有哪些潜在风险是它挡不住的。
10. **整体系统局限性**：如果将这套 Harness 直接部署到真实企业生产环境，最薄弱的环节在哪里？

#### 本题如何测试与验收

这是人工设计复盘，没有 `tests/test_design_memo.py`。边实现边保存上述十问的证据，最后压缩成约 2 页文稿。

```powershell
# 获取当前机器的真实沙箱后端
uv run python -c "from cs329z_hw1 import sandbox; print(sandbox.jail())"
# 查看真实检索排序与记忆存储
uv run python -m cs329z_hw1.show bm25 'larchfield audit'
uv run python -m cs329z_hw1.show memory
# 最终代码回归；Live 会产生费用
uv run pytest -m 'not live'
Remove-Item Env:CS329Z_EVAL_SLICE -ErrorAction SilentlyContinue
uv run pytest -m live -s
```

- 为十个问题逐项勾选：有明确设计决定、有理由和代价、有真实代码位置或运行证据；BM25 使用你实际找到的失败查询，上面的示例查询不保证是失败案例。
- 协议、终端、压缩、记忆、审批分别引用对应测试或轨迹；引用记忆文件的真实内容来分析遗漏和事实更正，而不是只描述理想方案。
- “空承诺”需说明当前策略及误判风险；沙箱需结合当前 `none` 输出与 Windows 实现说明实际边界，不能声称存在操作系统隔离。
- 人工验收：约 2 页 `design_memo`，十问均覆盖且与实现一致；附可追溯的测试结果和轨迹路径。最终 Live 全量结果作为证据保存，文稿评阅不由 pytest 自动代替。

## 最终交付自检

- [ ] 第 1–15 题的适用离线测试全通，各项完整 Live 测试达到阈值，未残留切片设置。
- [ ] 每个 adapter 已接到实现；业务辅助代码均在 `cs329z_hw1/`，提供的接口与测试未被改动。
- [ ] 第 16 题有 1 页观察笔记、至少 5 个新请求及聊天轨迹。
- [ ] 第 17 题有 2 页备忘录、十问回答及可复查证据；保留仿真结果和记忆文件。
- [ ] 保留运行证据与费用统计；不将 `.env` 中的 API Key 放入代码、报告或提交。

## 分值分布总览

| 模块编号与名称 | 离线确定性测试分值 | 在线 Live 评测分值 | 单项合计 |
|---|---:|---:|---:|
| 1. `priority`（邮件优先级分类） | 1 | 2 | 3 |
| 2. `daily_digest`（每日工作简报） | 1 | 3 | 4 |
| 3. `bm25`（倒排索引检索器） | 8 | 0 | 8 |
| 4. `email_qa`（多跳邮件问答） | 2 | 6 | 8 |
| 5. `tool_registry`（工具注册表与校验） | 3 | 0 | 3 |
| 6. `tool_protocol`（自定义文本工具协议） | 2 | 2 | 4 |
| 7. `agent_loop`（Agent 主控制循环） | 8 | 0 | 8 |
| 8. `cardinal`（工具集组装与惰性加载） | 2 | 0 | 2 |
| 9. `search_docs`（文档检索与分页读取） | 2 | 3 | 5 |
| 10. `terminal`（终端执行与超大输出策略） | 2 | 4 | 6 |
| 11. `compaction`（长上下文压缩） | 5 | 3 | 8 |
| 12. `memory`（跨会话持久记忆） | 3 | 5 | 8 |
| 13. `interactive`（主动澄清、审批与中途转向） | 7 | 0 | 7 |
| 14. `guardrails`（拒绝规则与防提示注入） | 2 | 2 | 4 |
| 15. `sim_eval`（20 Personas 端到端模拟评测） | 0 | 10 | 10 |
| **代码自动评分小计** | **48** | **40** | **88** |
| 16. `field_notes`（交互实验观察记录） | — | — | 10 |
| 17. `design_memo`（系统架构设计备忘录） | — | — | 20 |
| **总分** | **48** | **40** | **118** |
