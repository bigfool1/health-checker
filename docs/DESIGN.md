# Health Assistant — Design Document

## Overview

健康助手系统，将原 Dify Workflow 实现迁移为 **FastAPI + LangGraph** 架构。

## Tech Stack

| 层 | 技术 | 职责 |
|---|---|---|
| API 层 | FastAPI | HTTP endpoint、会话管理 |
| 编排层 | LangGraph StateGraph | 意图路由、槽位填充、流程控制 |
| 理解层 | LLM（单节点） | 意图识别 + 类型分类 + 实体提取 |
| 工具层 | Mock storage | 记录/计划持久化（demo） |

## Architecture

```
用户输入
  │
  ▼
┌─────────────────┐
│  LLM 意图识别    │  ← 唯一调用 LLM 的地方
│  → action       │    提取 action + type + confidence + entities
│  → type         │    router prompt ~200 行，含优先级规则、模糊词、示例
│  → entities     │
└────────┬────────┘
         │
    ─────┼───── 条件边（纯代码路由，按 action）
         │
   ┌─────┼─────┬──────┐
   ▼     ▼     ▼      ▼
  ask  record set  ambiguous
             plan      │
              │        ▼
              │    澄清追问用户
              │
         ┌────┴──── 条件边（纯代码路由，按 type）
         ▼
       槽位填充节点（per-type 纯代码）
         │  water/diet/sport/mood 各一个
         │  ← 单位换算、默认值填充、泛词过滤、数值校验
         │
         ├── 缺失字段 → 模板追问
         │
         └── 完整 → 写入存储 → 模板确认回复
```

## Action / Type 体系

| action | 含义 | 路由目标 |
|--------|------|---------|
| record | 用户描述已发生的健康行为 | type 分支 → slot-fill |
| set_plan | 用户设置每日目标 | type 分支 → slot-fill |
| ask | 用户咨询健康问题 | handle_ask |
| ambiguous | 无法判断意图 | handle_ambiguous |

| type | record 必需字段 | set_plan 目标参数 |
|------|----------------|-------------------|
| water | beverage_name, amount_ml | target_ml |
| diet | cuisine_name, meal_time | count |
| sport | sport_name, duration_min | duration_min |
| mood | mood_label | count |

## Key Design Decisions

### 为什么 LLM 只用于意图识别

LLM 的价值在非结构化自然语言 → 结构化 JSON。下游的路由、字段检查、追问生成全部是有限状态空间内的确定性操作，用代码实现更可靠、可测试、低延迟。

### 为什么槽位填充追问不用 LLM

追问句式有限可枚举（type × missing_fields 的组合只有几十条模板）。用 LLM 生成引入不确定性和延迟，换不回对等的体验提升。

### 为什么每个 type 有独立的 slot-fill 节点

不同 type 的字段含义、单位转换、默认值、泛词列表完全不同——沉淀在 per-type 节点中，避免一个臃肿的通配函数。

### 为什么用 LangGraph

- 条件边（conditional_edges）天然映射 action/type 的分支路由
- StateGraph 的状态传递保证每一步可追溯
- 图结构与 Dify 工作流有直观对应关系，迁移叙事清晰

## Improvement Points vs Original Dify Workflow

1. **泛词过滤下沉到代码层** — prompt 指导 LLM 省去不必要的泛词，但即使 LLM 提取了模糊值（如"东西""不知道"），per-type 节点也会在代码层过滤，不依赖 LLM 的 prompt 遵守度
2. **默认值智能填充** — date（今天）、time_desc（当前时间）自动补充，减少追问
3. **type 强制互斥** — "跑完步喝了蛋白粉"同时涉及 sport 和 diet，当前只能二选一。对 demo 保持互斥是合理简化
4. **计划设置合理性校验** — target_ml > 50000 拦截等

## Module Structure

```
health_tracker/
├── config.py                  # 环境变量 LLM 配置
├── main.py                    # FastAPI + 会话管理
└── graph/
    ├── state.py               # GraphState TypedDict
    ├── templates.py           # 必填字段 schema + 追问模板
    ├── tools.py               # mock 存储
    ├── edges.py               # action/type 条件边路由
    ├── builder.py             # StateGraph 组装
    └── nodes/
        ├── _utils.py          # 共享工具（日期、换算、格式化）
        ├── intent.py          # LLM 意图识别（prompt ~200 行）
        ├── handlers.py        # ask / ambiguous handler
        ├── record/
        │   ├── water.py       # 单位换算（杯→ml）、泛词过滤
        │   ├── diet.py        # 餐次/就餐方式推断
        │   ├── sport.py       # 时长解析、卡路里估算
        │   └── mood.py        # 模糊情绪过滤
        └── set_plan/
            ├── water.py       # 合理性校验（上限拦截）
            ├── diet.py        # count 校验
            ├── sport.py       # duration 解析
            └── mood.py        # count 校验

prompts/                       # prompt 版本管理
│   (router prompt 当前版本维护在 intent.py 的 SYSTEM_PROMPT 中)
scripts/
└── test_intent.py             # 实时 LLM 意图识别测试

tests/
└── test_graph.py              # 38 个单元/集成测试

docs/
└── DESIGN.md                  # 本文件
```

## Current Status

- ✅ action/type 体系精简（删除 med、modify_delete）
- ✅ Router prompt 重写（~200 行，含 action 优先级、模糊词、时间解析、5 个示例）
- ✅ `_parse_json` 处理 `<think>` 标签（DS V4 Flash tagged reasoning 兼容）
- ✅ slot-fill 拆分为 8 个 per-type 节点
- ✅ 单位换算、默认值填充、泛词过滤代码层实现
- ✅ 38 个测试全部通过
