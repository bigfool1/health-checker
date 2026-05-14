# Health Assistant — Design Document

> [中文版 (Chinese)](./DESIGN.zh.md)

## Overview

A health assistant system migrated from a Dify Workflow implementation to a **FastAPI + LangGraph** architecture.

## Tech Stack

| Layer | Tech | Role |
|---|---|---|
| API | FastAPI | HTTP endpoint, session management |
| Orchestration | LangGraph StateGraph | Intent routing, slot-filling, flow control |
| Understanding | LLM (single node) | Intent classification + type + entity extraction |
| Tools | Mock storage | Record/plan persistence (demo) |

## Architecture

```
User Input
  │
  ▼
┌─────────────────┐
│  LLM Intent     │  ← The only LLM call
│  → action       │    Extracts action + type + confidence + entities
│  → type         │    Router prompt ~200 lines with priority rules,
│  → entities     │    vague words, and examples
└────────┬────────┘
         │
    ─────┼───── Conditional edges (pure code routing by action)
         │
   ┌─────┼─────┬──────┐
   ▼     ▼     ▼      ▼
  ask  record set  ambiguous
             plan      │
              │        ▼
              │    Prompt user for clarification
              │
         ┌────┴──── Conditional edges (pure code routing by type)
         ▼
       Per-type slot-fill nodes (pure code)
         │  One each for water/diet/sport/mood
         │  ← Unit conversion, defaults, vague-word filtering, validation
         │
         ├── Missing fields → template-based prompt
         │
         └── Complete → write to storage → template-based confirmation
```

## Action / Type System

| action | Meaning | Route target |
|--------|---------|-------------|
| record | User describes a completed health action | type branch → slot-fill |
| set_plan | User sets a daily goal | type branch → slot-fill |
| ask | User asks a health question | handle_ask |
| ambiguous | Intent cannot be determined | handle_ambiguous |

| type | record required fields | set_plan target params |
|------|----------------------|------------------------|
| water | beverage_name, amount_ml | target_ml |
| diet | cuisine_name, meal_time | count |
| sport | sport_name, duration_min | duration_min |
| mood | mood_label | count |

## Key Design Decisions

### Why LLM is only used for intent extraction

The LLM's value is unstructured natural language → structured JSON. Downstream routing, field validation, and prompt generation are all deterministic operations within a finite state space. Implementing them in code is more reliable, testable, and low-latency.

### Why slot-fill follow-ups don't use LLM

The set of follow-up prompts is finite and enumerable (type × missing_fields = only dozens of template combinations). Using LLM generation introduces uncertainty and latency without delivering proportional UX improvement.

### Why each type has its own slot-fill node

Different types have entirely different field semantics, unit conversions, defaults, and vague-word lists. Isolating these in per-type nodes avoids a bloated catch-all function.

### Why LangGraph

- Conditional edges naturally map to action/type branch routing
- StateGraph's state passing ensures every step is traceable
- The graph structure maps intuitively to the original Dify workflow, making the migration narrative clear

## Improvement Points vs Original Dify Workflow

1. **Vague-word filtering pushed to code layer** — the prompt guides the LLM to omit unnecessary vague words, but even if the LLM extracts fuzzy values (e.g., "stuff", "whatever"), per-type nodes filter them at the code level, without relying on LLM prompt compliance
2. **Smart default filling** — date (today), time_desc (current time) are auto-filled to reduce follow-up prompts
3. **Enforced type mutual exclusion** — "drank a protein shake after running" involves both sport and diet, but only one can be selected. Keeping them mutually exclusive is a reasonable simplification for a demo
4. **Plan sanity checks** — e.g., target_ml > 50000 is rejected

## Module Structure

```
health_tracker/
├── config.py                  # Env-based LLM config
├── main.py                    # FastAPI + session management
└── graph/
    ├── state.py               # GraphState TypedDict
    ├── templates.py           # Required field schema + follow-up templates
    ├── tools.py               # Mock storage
    ├── edges.py               # Action/type conditional edge routing
    ├── builder.py             # StateGraph assembly
    └── nodes/
        ├── _utils.py          # Shared utilities (date, conversion, formatting)
        ├── intent.py          # LLM intent extraction (prompt ~200 lines)
        ├── handlers.py        # ask / ambiguous handlers
        ├── record/
        │   ├── water.py       # Unit conversion (cup→ml), vague-word filtering
        │   ├── diet.py        # Meal time / dining style inference
        │   ├── sport.py       # Duration parsing, calorie estimation
        │   └── mood.py        # Vague mood filtering
        └── set_plan/
            ├── water.py       # Sanity check (upper limit rejection)
            ├── diet.py        # count validation
            ├── sport.py       # Duration parsing
            └── mood.py        # count validation

prompts/                       # Prompt versioning
│   (current router prompt maintained in intent.py SYSTEM_PROMPT)
scripts/
└── test_intent.py             # Live LLM intent extraction test

tests/
└── test_graph.py              # 38 unit/integration tests

docs/
└── DESIGN.md                  # This file
```

## Current Status

- ✅ Action/type system simplified (removed med, modify_delete)
- ✅ Router prompt rewritten (~200 lines, with action priority, vague words, time parsing, 5 examples)
- ✅ `_parse_json` handles `<think>` tags (DS V4 Flash tagged reasoning compatibility)
- ✅ Slot-fill split into 8 per-type nodes
- ✅ Unit conversion, default filling, vague-word filtering implemented at code level
- ✅ All 38 tests passing
