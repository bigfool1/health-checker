"""
Live LLM edge case test — observe full pipeline: LLM intent → slot-fill.
Usage: DEEPSEEK_API_KEY=sk-xxx .venv/bin/python scripts/test_edge_cases.py
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_anthropic import ChatAnthropic
from health_tracker.graph.builder import build_graph
from health_tracker.graph.state import GraphState

EDGE_CASES = [
    # (label, input)
    ("missing verb", "一杯咖啡"),
    ("negation", "今天没喝水"),
    ("health-adjacent", "我好渴"),
    ("mixed signals", "每天跑步，今天吃了沙拉"),
    ("gibberish", "asdfgh"),
    ("self-correction", "喝了咖啡不对是茶"),
    ("question as statement", "喝了多少水算健康"),
    ("very short", "水"),
    ("implicit mood", "烦"),
    ("multiple items", "喝了一杯咖啡吃了沙拉"),
    ("vague all", "吃了点东西"),
    ("set plan edge", "我想减肥"),
]


async def run_case(graph, label: str, user_input: str) -> dict:
    state: GraphState = {
        "user_input": user_input, "context": "",
        "action": None, "type": None,
        "entities": {}, "pending_entities": {}, "missing_fields": [], "response": "",
    }
    t0 = time.monotonic()
    result = await graph.ainvoke(state)
    elapsed = time.monotonic() - t0
    return {
        "label": label,
        "input": user_input,
        "action": result.get("action"),
        "type": result.get("type"),
        "confidence": result.get("confidence"),
        "entities": result.get("entities", {}),
        "missing_fields": result.get("missing_fields", []),
        "response": result.get("response", ""),
        "latency_ms": round(elapsed * 1000),
    }


async def main():
    api_key = os.getenv("DEEPSEEK_API_KEY", "sk-xxx")
    model = os.getenv("LLM_MODEL", "deepseek-v4-flash")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/anthropic")

    print(f"Model: {model}  |  base: {base_url}")
    print()

    llm = ChatAnthropic(model=model, api_key=api_key, base_url=base_url, temperature=0)
    graph = build_graph(llm)

    latencies = []

    for i, (label, user_input) in enumerate(EDGE_CASES):
        print(f"[{i+1}/{len(EDGE_CASES)}] {label}")
        print(f"     input: {user_input}")

        r = await run_case(graph, label, user_input)
        latencies.append(r["latency_ms"])

        ents = json.dumps(r["entities"], ensure_ascii=False)
        print(f"     action={r['action']}  type={r['type']}  confidence={r['confidence']}  missing={r['missing_fields']}")
        print(f"     entities={ents}")
        print(f"     response={r['response'][:120]}")
        print(f"     latency={r['latency_ms']}ms")
        print()

    avg = sum(latencies) / len(latencies) if latencies else 0
    print(f"---")
    print(f"latency: min={min(latencies)}ms  max={max(latencies)}ms  avg={avg:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())
