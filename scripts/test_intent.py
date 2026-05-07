"""
Live LLM test for intent extraction.
Runs test cases from the router prompt against the real LLM, measures latency.
Usage: DEEPSEEK_API_KEY=sk-xxx .venv/bin/python scripts/test_intent.py
"""
import asyncio
import json
import os
import time

# ensure project root on path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_anthropic import ChatAnthropic
from health_tracker.graph.builder import build_graph
from health_tracker.graph.state import GraphState

TEST_CASES = [
    # (label, user_input, expected)
    ("water record (precise)", "刚才喝了一杯咖啡",
     {"action": "record", "type": "water"}),
    ("water record (vague)", "我刚刚喝了一杯东西",
     {"action": "record", "type": "water"}),
    ("diet record", "今天午饭吃了牛排，在餐厅",
     {"action": "record", "type": "diet"}),
    ("sport record", "今天跑步30分钟",
     {"action": "record", "type": "sport"}),
    ("mood record (vague)", "我今天不太开心",
     {"action": "record", "type": "mood"}),
    ("set_plan water", "每天喝2000ml水",
     {"action": "set_plan", "type": "water"}),
    ("ask nutrition", "这道菜多少热量",
     {"action": "ask", "type": "none"}),
    ("ask diet plan", "有没有减肥食谱？",
     {"action": "ask", "type": "diet"}),
    ("ambiguous", "嗯",
     {"action": "ambiguous"}),
    ("sport set_plan", "我要坚持每天运动45分钟",
     {"action": "set_plan", "type": "sport"}),
    ("water record time", "早上喝了一杯牛奶",
     {"action": "record", "type": "water"}),
    ("mood record explicit", "今天心情特别好，开心",
     {"action": "record", "type": "mood"}),
]


async def run_one(graph, label: str, user_input: str) -> dict:
    state: GraphState = {
        "user_input": user_input,
        "context": "",
        "action": None,
        "type": None,
        "entities": {},
        "pending_entities": {},
        "missing_fields": [],
        "response": "",
    }
    t0 = time.monotonic()
    result = await graph.ainvoke(state)
    elapsed = time.monotonic() - t0
    return {
        "label": label,
        "input": user_input,
        "action": result.get("action"),
        "type": result.get("type"),
        "entities": result.get("entities", {}),
        "response": result.get("response", ""),
        "latency_ms": round(elapsed * 1000),
    }


def check(result: dict, expected: dict) -> list[str]:
    issues = []
    for key, val in expected.items():
        actual = result.get(key)
        if actual != val:
            issues.append(f"  {key}: expected={val!r}, got={actual!r}")

    # extra checks per case
    if result["label"] == "water record (vague)":
        if result["entities"].get("beverage_name") is not None:
            issues.append("  beverage_name should be null for vague '东西'")
    if result["label"] == "mood record (vague)":
        if result["entities"].get("mood_label") is not None:
            issues.append("  mood_label should be null for vague '不太开心'")
    if result["label"] == "set_plan water":
        if result["entities"].get("target_ml") != 2000:
            issues.append(f"  target_ml expected 2000, got {result['entities'].get('target_ml')}")
    if result["label"] == "sport set_plan":
        if result["entities"].get("duration_min") != 45:
            issues.append(f"  duration_min expected 45, got {result['entities'].get('duration_min')}")
    if result["label"] == "water record time":
        ents = result.get("entities", {})
        if ents.get("time_desc") != "08:00" and ents.get("time_desc") != "早上":
            issues.append(f"  time_desc should be 早上 or 08:00, got {ents.get('time_desc')}")
        if ents.get("beverage_name") != "牛奶":
            issues.append(f"  beverage_name should be 牛奶, got {ents.get('beverage_name')}")
    if result["label"] == "mood record explicit":
        ents = result.get("entities", {})
        if ents.get("mood_label") != "开心":
            issues.append(f"  mood_label should be 开心, got {ents.get('mood_label')}")
    return issues


async def main():
    api_key = os.getenv("DEEPSEEK_API_KEY", "sk-xxx")
    model = os.getenv("LLM_MODEL", "deepseek-v4-flash")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/anthropic")

    print(f"Model: {model}")
    print(f"Base:  {base_url}")
    print(f"Key:   {'***' + api_key[-4:] if len(api_key) > 10 else 'NOT SET'}")
    print()

    llm = ChatAnthropic(model=model, api_key=api_key, base_url=base_url, temperature=0)
    graph = build_graph(llm)

    total = len(TEST_CASES)
    passed = 0
    latencies = []

    for i, (label, user_input, expected) in enumerate(TEST_CASES):
        print(f"[{i+1}/{total}] {label}")
        print(f"       input: {user_input}")

        result = await run_one(graph, label, user_input)
        latencies.append(result["latency_ms"])

        issues = check(result, expected)
        if issues:
            print(f"       \033[31mFAIL\033[0m ({result['latency_ms']}ms)")
            print(f"       action={result['action']}, type={result['type']}")
            print(f"       entities={json.dumps(result['entities'], ensure_ascii=False)}")
            for issue in issues:
                print(issue)
        else:
            print(f"       \033[32mPASS\033[0m ({result['latency_ms']}ms) action={result['action']}, type={result['type']}, entities={json.dumps(result['entities'], ensure_ascii=False)}")
            passed += 1
        print()

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    print(f"---")
    print(f"Result: {passed}/{total} passed")
    print(f"Latency: min={min(latencies)}ms, max={max(latencies)}ms, avg={avg_latency:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())
