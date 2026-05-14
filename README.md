# Health Tracker

A health assistant built with [LangGraph](https://github.com/langchain-ai/langgraph) + FastAPI, migrated from a [Dify](https://dify.ai) workflow. Demonstrates architectural patterns for LLM applications.

> [中文版 (Chinese)](./README.zh.md)

## Features

Users record health data (water, diet, sport, mood) and set daily goals via natural language:

```
"Just had two cups of coffee"  →  record / water  →  Recorded: coffee, 2 cups, 500ml
"Exercise 45 min daily"        →  set_plan / sport →  Goal set: 45 min sport
"How many calories in this"    →  ask / none       →  Q&A (WIP)
"Hmm"                          →  ambiguous        →  Clarification prompt
```

## Architecture

| Layer | Tech | Role |
|---|---|---|
| API | FastAPI | HTTP endpoint, session management |
| Orchestration | LangGraph StateGraph | Intent routing, slot-filling, flow control |
| Understanding | DeepSeek V4 Flash (single node) | Intent + type + entity extraction |
| Storage | In-memory (demo) | Record / plan persistence |

```
User Input
  │
  ▼
┌──────────────┐
│ LLM Intent   │  ← The only LLM call
│ → JSON       │    Router prompt ~200 lines
└──────┬───────┘
       │
  ─────┼───── Action routing (pure code)
       │
  ┌────┼────┬──────┐
  ▼    ▼    ▼      ▼
 ask  rec  set  ambiguous
           plan     │
           │        ▼
           │    Clarification
           │
      ┌────┴──── Type routing (pure code)
      ▼
  Per-type slot-fill (pure code)
   ← Unit conversion, defaults, vague-word filtering
      │
      ├── Missing fields → template-based prompt
      └── Complete       → write → confirm
```

**LLM only does semantic extraction.** Routing, field validation, and prompt generation are all deterministic code — low latency, testable, consistent behavior.

**Template-based follow-ups, not LLM.** The set of follow-up prompts is finite and enumerable. Code templates are faster and more stable than LLM generation.

## Running

```bash
export DEEPSEEK_API_KEY=your-key

uv sync
uv run python -m health_tracker.main

# Test
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "drank three cups of water today"}'

# Live LLM intent test
uv run python scripts/test_intent.py
```

## Tests

```bash
uv run pytest tests/ -v
```

38 tests covering templates, routing, JSON parsing (including `<think>` tags), per-type slot-fill, graph structure, and end-to-end mock-LLM flows. No API key needed.

## Project Structure

```
health_tracker/
├── config.py              # LLM config (DeepSeek Anthropic-compatible endpoint)
├── main.py                # FastAPI + session management
└── graph/
    ├── state.py           # GraphState
    ├── templates.py       # Required fields + follow-up templates
    ├── tools.py           # Mock storage
    ├── edges.py           # Action/type conditional edges
    ├── builder.py         # StateGraph assembly
    └── nodes/
        ├── _utils.py      # Shared utilities
        ├── intent.py      # LLM intent extraction
        ├── handlers.py    # ask / ambiguous handlers
        ├── record/        # 4 per-type record nodes
        └── set_plan/      # 4 per-type plan nodes
scripts/
└── test_intent.py         # Live LLM test
tests/
└── test_graph.py          # 38 unit/integration tests
docs/
└── DESIGN.md              # Architecture design doc
```

## Design Principles

1. **LLM only when necessary** — single node for semantic extraction; everything downstream is deterministic code
2. **Code-level safety net** — vague-word filtering and default value filling happen in slot-fill nodes as a second pass
3. **Per-type separation of concerns** — each health type has its own slot-fill, maintaining its own unit conversions and vague-word lists
4. **No structured output** — DS V4 Flash's structured_output has compatibility issues with nested objects. Uses text output + `_parse_json()` (supports `<think>` tags, ```json fences, plain JSON)
