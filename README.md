# Health Tracker

健康助手系统，基于 [LangGraph](https://github.com/langchain-ai/langgraph) + FastAPI，从 [Dify](https://dify.ai) workflow 迁移而来，演示 LLM 应用的架构设计。

## 功能

用户通过自然语言记录健康数据（喝水、饮食、运动、心情）和设置每日目标：

```
"刚才喝了两杯咖啡"  →  record / water  →  已记录喝水：咖啡，两杯，500ml
"每天运动45分钟"    →  set_plan / sport →  已设置运动目标：45 分钟
"这道菜多少热量"    →  ask / none       →  问答开发中
"嗯"               →  ambiguous        →  澄清追问
```

## 架构

| 层 | 技术 | 职责 |
|---|------|------|
| API | FastAPI | HTTP endpoint、会话管理 |
| 编排 | LangGraph StateGraph | 意图路由、槽位填充、流程控制 |
| 理解 | DeepSeek V4 Flash（单节点） | 意图 + type + entities 提取 |
| 存储 | In-memory（demo） | 记录 / 计划持久化 |

```
用户输入
  │
  ▼
┌──────────────┐
│ LLM 意图识别  │  ← 唯一 LLM 调用
│ → JSON       │    router prompt ~200 行
└──────┬───────┘
       │
  ─────┼───── action 路由（纯代码）
       │
  ┌────┼────┬──────┐
  ▼    ▼    ▼      ▼
 ask  rec  set  ambiguous
           plan     │
           │        ▼
           │    澄清追问
           │
      ┌────┴──── type 路由（纯代码）
      ▼
  槽位填充（per-type 纯代码）
   ← 单位换算、默认值、泛词过滤
      │
      ├── 缺字段 → 模板追问
      └── 完整   → 写入 → 确认
```

**LLM 只做语义提取。** 路由、字段检查、追问生成全是确定性代码，低延迟、可测试、行为一致。

**模板追问，不用 LLM。** 追问句式有限可枚举，代码模板比 LLM 生成更快更稳定。

## 运行

```bash
export DEEPSEEK_API_KEY=your-key

uv sync
uv run python -m health_tracker.main

# 测试
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "今天喝了三杯水"}'

# 实时 LLM 意图测试
uv run python scripts/test_intent.py
```

## 测试

```bash
uv run pytest tests/ -v
```

38 个测试，覆盖模板、路由、JSON 解析（含 `<think>` 标签）、per-type slot-fill、图结构、端到端 mock-LLM 流程。无需 API key。

## 项目结构

```
health_tracker/
├── config.py              # LLM 配置（DeepSeek Anthropic 兼容端点）
├── main.py                # FastAPI + 会话管理
└── graph/
    ├── state.py           # GraphState
    ├── templates.py       # 必填字段 + 追问模板
    ├── tools.py           # mock 存储
    ├── edges.py           # action/type 条件边
    ├── builder.py         # StateGraph 组装
    └── nodes/
        ├── _utils.py      # 共享工具
        ├── intent.py      # LLM 意图识别
        ├── handlers.py    # ask / ambiguous
        ├── record/        # 4 个 per-type 记录节点
        └── set_plan/      # 4 个 per-type 计划节点
scripts/
└── test_intent.py         # 实时 LLM 测试
tests/
└── test_graph.py          # 38 个单元/集成测试
docs/
└── DESIGN.md              # 架构设计文档
```

## 设计原则

1. **LLM 只在必要时使用** — 单节点做语义提取，下游全是确定性代码
2. **代码层做兜底** — 泛词过滤、默认值填充在 slot-fill 节点中二次校验
3. **Per-type 职责分离** — 每种健康类型独立 slot-fill，各自维护单位换算和泛词列表
4. **结构化输出关闭** — DS V4 Flash 的 structured_output 对嵌套 object 有兼容问题，改为 text 输出 + `_parse_json()` 解析（支持 `<think>` 标签、```json 围栏、纯 JSON）
