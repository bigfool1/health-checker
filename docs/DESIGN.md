# Health Assistant — Design Document

## Overview

健康助手系统，将原 Dify Workflow + Django 实现迁移为 **FastAPI + LangGraph** 架构。

## Tech Stack

| 层 | 技术 | 职责 |
|---|---|---|
| API 层 | FastAPI + async SQLAlchemy 2.0 | CRUD endpoint、tool endpoint |
| 编排层 | LangGraph StateGraph | 意图路由、槽位填充、流程控制 |
| 理解层 | LLM 单节点 | 意图识别 + 类型分类 + 实体提取 |
| 工具层 | FastAPI endpoint → LangChain BaseTool | CRUD 能力暴露给 LangGraph graph |

## Architecture

```
用户输入
  │
  ▼
┌─────────────────┐
│  LLM 意图识别    │  ← 唯一调用 LLM 的地方
│  → action       │    提取 action + type + entities
│  → type         │
│  → entities     │
└────────┬────────┘
         │
    ┌────┴───── 条件边（纯代码路由）
    │
 ┌──┼──┬──────┬──────────┐
 ▼  ▼  ▼      ▼          ▼
ask rec set  modify  ambiguous
    plan  delete    │
    │     │         ▼
    │     │    澄清追问用户
    │     │
    └──┬──┘
       │ 条件边：type → water / diet / sport / mood / med
       ▼
   槽位填充节点（纯代码）
       │
       ├── 缺失字段 → 模板追问
       │
       └── 完整 → CRUD tool 调用
                     │
                     ▼
                 模板确认回复
```

## Original Workflow Analysis

### Strengths
- 单 LLM 节点做提取，经济高效
- action/type 两层路由，职责清晰
- 槽位填充不做语义理解，只做字段检查

### Improvement Points

1. **缺少纠错意图（correct）** — 用户说"诶不对，刚才那杯水是 200ml 不是 300ml"，当前 `modify_delete` 无法覆盖自然语言的修正。新增 `action: correct`
2. **type 强制互斥** — "跑完步喝了蛋白粉"同时涉及 sport 和 diet，当前只能二选一。对 demo 保持互斥是合理简化
3. **ambiguous 降级策略** — 依赖 LLM 自我校准，部分模型会过度自信。可加置信度阈值
4. **写入后确认回复缺失** — 原设计没有定义写入成功后的用户回复格式
5. **计划设置缺少合理性校验** — `target_ml: 99999` 需要代码层校验

## Workflow Detail

### Step 1 — LLM 意图识别

```
输入: 用户自然语言
输出: {
  "action": "record | set_plan | modify_delete | ask | ambiguous | correct",
  "type": "water | sport | diet | mood | med | none",
  "entities": {...}
}
```

### Step 2 — Action 路由（条件边，纯代码）

| action | 目标 |
|--------|------|
| ask | 问答流程 |
| record | 记录流程（按 type 分支） |
| set_plan | 计划设置流程（按 type 分支） |
| modify_delete | 记录修改/删除流程 |
| correct | 纠错流程（根据上文修正记录） |
| ambiguous | 澄清追问，引导用户重述 |

### Step 3 — Type 路由（条件边，纯代码）

record / set_plan 下根据 type 进入对应子节点：

| type | record 必需字段 | set_plan 目标参数 |
|------|----------------|-------------------|
| water | beverage_name, amount_desc, time_desc | target_ml |
| diet | cuisine_name, date, dining_method | count |
| sport | sport_name, duration_min, total_calories | duration_min |
| mood | mood_label, date | count |
| med | med_name | med_name, times_per_day |

### Step 4 — 槽位填充（纯代码）

- 对比 entities 与 required_fields
- 缺失 → 模板追问（代码枚举，不调 LLM）
- 完整 → 调用 CRUD tool 写入

### Step 5 — 确认回复（模板化）

写入成功后，模板拼装确认信息返回用户。

## Key Design Decisions

### 为什么 LLM 只用于意图识别

LLM 的价值在非结构化自然语言 → 结构化 JSON。下游的路由、字段检查、追问生成全部是有限状态空间内的确定性操作，用代码实现更可靠、可测试、低延迟。

### 为什么槽位填充追问不用 LLM

追问句式有限可枚举（type × missing_fields 的组合最多几十条模板）。用 LLM 生成引入不确定性和延迟，换不回对等的体验提升。这个取舍在面试叙事中有明确论证价值。

### 为什么用 LangGraph

- 条件边（conditional_edges）天然映射 action/type 的分支路由
- StateGraph 的状态传递保证每一步可追溯
- checkpointing 便于调试和面试演示
- 图结构与 Dify 工作流有直观对应关系，迁移叙事清晰

## Module Division

```
lang_stuff/
├── api/                    # FastAPI 应用
│   ├── routers/            # CRUD 路由
│   │   ├── water.py
│   │   ├── diet.py
│   │   ├── sport.py
│   │   ├── mood.py
│   │   └── med.py
│   ├── schemas/            # Pydantic models
│   └── deps.py             # 依赖注入
├── core/                   # 领域逻辑
│   ├── models.py           # SQLAlchemy ORM 模型
│   ├── database.py         # async engine / session
│   └── tools.py            # LangChain tool 定义
├── graph/                  # LangGraph 工作流
│   ├── state.py            # GraphState 定义
│   ├── nodes/
│   │   ├── intent.py       # LLM 意图识别节点
│   │   ├── slot_fill.py    # 槽位填充节点
│   │   └── ask.py          # 问答节点
│   ├── edges.py            # 条件边路由逻辑
│   └── builder.py          # StateGraph 组装
├── prompts/                # LLM prompt 模板
│   └── intent.yaml         # 意图识别 prompt
├── config.py               # 配置
└── main.py                 # 启动入口
```

## TODO

### Phase 1 — 基础设施
- [ ] FastAPI 项目骨架搭建，async engine/session 配置
- [ ] SQLAlchemy ORM 模型定义（Water, Diet, Sport, Mood, Med, Plan）
- [ ] Alembic 迁移初始化

### Phase 2 — CRUD API
- [ ] 五类健康记录的 CRUD endpoint
- [ ] 计划设置的 CRUD endpoint
- [ ] Pydantic schema 定义

### Phase 3 — LangGraph 工作流
- [ ] GraphState 与意图识别 prompt 设计
- [ ] LLM 意图识别节点实现
- [ ] 条件边路由逻辑（action → type → slot_fill）
- [ ] 槽位填充节点（字段检查 + 模板追问）

### Phase 4 — Tool 集成
- [ ] LangChain BaseTool 封装 CRUD 能力
- [ ] Tool 注册到 LangGraph graph

### Phase 5 — 完善
- [ ] correct 纠错意图实现
- [ ] ambiguous 置信度降级策略
- [ ] 写入成功模板确认回复
- [ ] 计划参数合理性校验
- [ ] 结构化日志 / checkpointing 可观测性

### Phase 6 — Demo 就绪
- [ ] README 架构说明与运行指南
- [ ] 示例对话脚本
- [ ] 可选：简单 Web UI 或 API 文档展示
