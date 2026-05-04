# Health Tracker

A health tracking assistant that migrates a [Dify](https://dify.ai) workflow to [LangGraph](https://github.com/langchain-ai/langgraph), demonstrating thoughtful LLM integration patterns.

## What It Does

Users log health data (water, diet, sport, mood, medication) via natural language. The system extracts intent and entities, routes through structured flows, and persists data — using an LLM only where it adds value.

```
"I drank two cups of coffee today"  →  extracts action=record, type=water,
                                      entities={beverage: coffee, amount: 2 cups, time: today}
                                      →  writes record → "Logged: coffee, 2 cups, today"

"I set a goal of 2000ml water daily" →  action=set_plan, type=water, target_ml=2000
                                      →  writes plan → "Goal set: 2000ml"
```

## Architecture

| Layer | Stack | Role |
|-------|-------|------|
| API | FastAPI | HTTP endpoints, session management |
| Orchestration | LangGraph StateGraph | Intent routing, slot-filling, flow control |
| Understanding | LLM (single node) | Intent + type + entity extraction |
| Storage | In-memory (mock) | Record / plan persistence |

```
User Input
    │
    ▼
┌──────────────┐
│ LLM Intent   │  ← only LLM call: extracts action, type, entities
│ Extraction   │
└──────┬───────┘
       │
  ─────┼───── conditional edges (pure code routing)
       │
  ┌────┼────┬──────┬───────────┐
  ▼    ▼    ▼      ▼           ▼
 ask  rec  set  modify   ambiguous
       plan  delete
       │
       ├── type routing → water/diet/sport/mood/med
       ▼
  Slot-Filling (pure code)
       │
       ├── missing → template follow-up
       └── complete → write → confirmation
```

## Key Design Decisions

**LLM only for semantic extraction.** A single LLM node converts unstructured natural language into structured JSON (action + type + entities). Everything downstream — routing, field checking, follow-up prompts — is deterministic code. This keeps latency low and behavior predictable where it matters.

**Template-based follow-ups, not LLM.** When a slot is missing, the system uses pre-defined question templates rather than generating questions with the LLM. The question space is finite and enumerable (~50 templates cover all type × field combinations). An LLM here would add latency and non-determinism without proportional UX gain.

**LangGraph for workflow state management.** Conditional edges naturally map to the action/type routing logic. StateGraph makes each step traceable with checkpointing, and the graph structure mirrors the original Dify workflow for clear migration narrative.

## Running

```bash
# set your API key (DeepSeek Anthropic-compatible endpoint)
export DEEPSEEK_API_KEY=your-key

# install & run
uv sync
uv run python -m health_tracker.main

# test
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "I drank two cups of coffee this morning"}'
```

## Tests

```bash
uv run pytest tests/ -v
```

39 tests covering templates, routing, slot-filling, JSON parsing, graph structure, and full graph flows with mocked LLM. No API key required.

## Project Structure

```
health_tracker/
├── config.py             # env-based LLM config
├── main.py               # FastAPI app + session store
└── graph/
    ├── state.py          # GraphState definition
    ├── templates.py      # required fields + question prompts
    ├── tools.py          # mock storage
    ├── edges.py          # conditional edge routing
    ├── builder.py        # StateGraph assembly
    └── nodes/
        ├── intent.py     # LLM intent extraction
        ├── slot_fill.py  # slot-filling logic
        └── handlers.py   # ask/ambiguous/modify_delete handlers
```

## Notes

This is a portfolio project demonstrating architecture decisions for LLM-powered applications. The original system runs on Django + Dify in production. This version re-implements the workflow in LangGraph with FastAPI, showing how to balance LLM and deterministic code in a real-world health tracking scenario.
