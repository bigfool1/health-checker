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
from health_tracker.config import LLM_THINKING
from health_tracker.graph.builder import build_graph
from health_tracker.graph.state import GraphState

SINGLE_TURN_CASES = [
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

# Multi-turn: each case = (label, [(turn_label, user_input, expected, extra_checks_fn), ...])
# pending_entities is carried automatically between turns
MULTI_TURN_CASES = [
    # ── basic cross-turn slot-fill ──
    (
        "multi: vague drink → specify",
        [
            ("T1 vague", "喝了一杯东西",
             {"action": "record", "type": "water"},
             lambda r: r["entities"].get("beverage_name") is None and "饮品" in r["response"]),
            ("T2 specify", "咖啡",
             {"action": "record", "type": "water"},
             lambda r: "已记录喝水" in r["response"]),
        ],
    ),
    (
        "multi: missing sport name → fill",
        [
            ("T1 no name", "今天运动了",
             {"action": "record", "type": "sport"},
             lambda r: r["entities"].get("sport_name") is None and ("运动" in r["response"] or "什么" in r["response"])),
            ("T2 fill both", "跑步半小时",
             {"action": "record", "type": "sport"},
             lambda r: "已记录运动" in r["response"]),
        ],
    ),
    (
        "multi: missing meal → fill",
        [
            ("T1 no meal", "吃了饭",
             {"action": "record", "type": "diet"},
             lambda r: "吃了什么" in r["response"] or "餐" in r["response"]),
            ("T2 fill", "午餐吃的沙拉",
             {"action": "record", "type": "diet"},
             lambda r: "已记录饮食" in r["response"]),
        ],
    ),
    # ── online bug: 5-turn water record ──
    (
        "multi: bug-repro 5-turn water",
        [
            ("T1 greet", "你好",
             {"action": "ambiguous"},
             lambda r: True),  # just accept anything
            ("T2 vague water", "我刚刚喝了水",
             {"action": "record", "type": "water"},
             lambda r: ("beverage_name" in r.get("missing_fields", []) or
                        "amount" in r.get("missing_fields", []))),
            ("T3 both info", "一杯白开水",
             {"action": "record", "type": "water"},
             lambda r: True),  # key check: should have both fields, but may not
            ("T4 amount only", "500ml",
             {"action": "record", "type": "water"},
             lambda r: True),
            ("T5 beverage only", "白水",
             {"action": "record", "type": "water"},
             lambda r: "已记录喝水" in r["response"]),  # must succeed by T5
        ],
    ),
]


async def run_one(graph, label: str, user_input: str,
                  context: str = "", pending_entities: dict | None = None) -> dict:
    state: GraphState = {
        "user_input": user_input,
        "context": context,
        "action": None,
        "type": None,
        "entities": {},
        "pending_entities": pending_entities or {},
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
        "missing_fields": result.get("missing_fields", []),
        "pending_entities": result.get("pending_entities", {}),
        "response": result.get("response", ""),
        "latency_ms": round(elapsed * 1000),
    }


def check_single(result: dict, expected: dict) -> list[str]:
    issues = []
    for key, val in expected.items():
        actual = result.get(key)
        if actual != val:
            issues.append(f"  {key}: expected={val!r}, got={actual!r}")

    label = result["label"]
    if label == "water record (vague)":
        if result["entities"].get("beverage_name") is not None:
            issues.append("  beverage_name should be null for vague '东西'")
    if label == "mood record (vague)":
        if result["entities"].get("mood_label") is not None:
            issues.append("  mood_label should be null for vague '不太开心'")
    if label == "set_plan water":
        if result["entities"].get("target_ml") != 2000:
            issues.append(f"  target_ml expected 2000, got {result['entities'].get('target_ml')}")
    if label == "sport set_plan":
        if result["entities"].get("duration_min") != 45:
            issues.append(f"  duration_min expected 45, got {result['entities'].get('duration_min')}")
    if label == "water record time":
        ents = result.get("entities", {})
        if ents.get("time_desc") != "08:00" and ents.get("time_desc") != "早上":
            issues.append(f"  time_desc should be 早上 or 08:00, got {ents.get('time_desc')}")
        if ents.get("beverage_name") != "牛奶":
            issues.append(f"  beverage_name should be 牛奶, got {ents.get('beverage_name')}")
    if label == "mood record explicit":
        ents = result.get("entities", {})
        if ents.get("mood_label") != "开心":
            issues.append(f"  mood_label should be 开心, got {ents.get('mood_label')}")
    return issues


def build_context(result: dict) -> str:
    """Build context string for the next turn, mirroring main.py's logic."""
    pending = result.get("pending_entities", {})
    if not pending:
        return ""
    rtype = result.get("type", "")
    missing = result.get("missing_fields", [])
    last_resp = result.get("response", "")
    return (
        f"上一轮对话中，用户正在记录{rtype}，"
        f"但还缺少以下信息：{', '.join(missing)}。"
        f"系统追问了：「{last_resp}」"
        f"当前用户输入可能是对这些缺失信息的补充，请据此提取 entities。"
    )


async def run_multi_turn(graph, label: str, turns: list) -> tuple[bool, list[str], list[dict]]:
    """Run a multi-turn case. Returns (passed, turn_results_detail, all_results)."""
    pending = {}
    all_results = []
    details = []
    passed = True

    for turn_label, user_input, expected, extra_check in turns:
        # build context from previous turn's state
        ctx = ""
        if pending:
            ctx = build_context(all_results[-1]) if all_results else ""

        result = await run_one(graph, f"{label}/{turn_label}", user_input,
                               context=ctx, pending_entities=pending)

        # carry pending forward
        pending = result["pending_entities"]
        all_results.append(result)

        # check expected action/type
        turn_issues = []
        for key, val in expected.items():
            actual = result.get(key)
            if actual is not None and actual != val:
                turn_issues.append(f"  {key}: expected={val!r}, got={actual!r}")

        # extra check
        if extra_check and not extra_check(result):
            turn_issues.append("  extra check failed")

        ok = len(turn_issues) == 0
        if not ok:
            passed = False

        details.append(
            f"  {turn_label}: {'PASS' if ok else 'FAIL'} "
            f"input={user_input!r} → action={result['action']}, type={result['type']}, "
            f"missing={result['missing_fields']}, "
            f"pending_keys={list(result['pending_entities'].keys())}, "
            f"resp={result['response'][:60]}"
        )
        for issue in turn_issues:
            details.append(f"    {issue}")
        details.append(f"    entities={json.dumps(result['entities'], ensure_ascii=False)}")

    return passed, details, all_results


async def main():
    api_key = os.getenv("DEEPSEEK_API_KEY", "sk-xxx")
    model = os.getenv("LLM_MODEL", "deepseek-v4-flash")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/anthropic")

    print(f"Model: {model}")
    print(f"Base:  {base_url}")
    print(f"Thinking: {LLM_THINKING}")
    print(f"Key:   {'***' + api_key[-4:] if len(api_key) > 10 else 'NOT SET'}")
    print()

    _thinking = {"type": "enabled", "budget_tokens": 512} if LLM_THINKING == "enabled" else {"type": "disabled"}
    llm = ChatAnthropic(model=model, api_key=api_key, base_url=base_url, temperature=0, thinking=_thinking)
    graph = build_graph(llm)

    # ── single-turn ──
    total_single = len(SINGLE_TURN_CASES)
    passed_single = 0
    latencies = []

    print("═══ Single-turn ═══")
    for i, (label, user_input, expected) in enumerate(SINGLE_TURN_CASES):
        print(f"[{i+1}/{total_single}] {label}")
        print(f"       input: {user_input}")

        result = await run_one(graph, label, user_input)
        latencies.append(result["latency_ms"])

        issues = check_single(result, expected)
        if issues:
            print(f"       \033[31mFAIL\033[0m ({result['latency_ms']}ms)")
            print(f"       action={result['action']}, type={result['type']}")
            print(f"       entities={json.dumps(result['entities'], ensure_ascii=False)}")
            for issue in issues:
                print(issue)
        else:
            print(f"       \033[32mPASS\033[0m ({result['latency_ms']}ms) action={result['action']}, type={result['type']}, entities={json.dumps(result['entities'], ensure_ascii=False)}")
            passed_single += 1
        print()

    avg_single = sum(latencies) / len(latencies) if latencies else 0
    print(f"Single-turn: {passed_single}/{total_single} passed, avg {avg_single:.0f}ms")
    print()

    # ── multi-turn ──
    total_multi = len(MULTI_TURN_CASES)
    passed_multi = 0

    print("═══ Multi-turn ═══")
    for i, (label, turns) in enumerate(MULTI_TURN_CASES):
        print(f"[{i+1}/{total_multi}] {label} ({len(turns)} turns)")

        ok, details, all_results = await run_multi_turn(graph, label, turns)
        for d in details:
            print(d)

        if ok:
            print(f"  \033[32mOVERALL PASS\033[0m")
            passed_multi += 1
        else:
            print(f"  \033[31mOVERALL FAIL\033[0m")
        print()

    print("---")
    print(f"Single-turn: {passed_single}/{total_single} passed, avg {avg_single:.0f}ms")
    print(f"Multi-turn:  {passed_multi}/{total_multi} passed")
    print(f"Total:       {passed_single + passed_multi}/{total_single + total_multi} passed")


if __name__ == "__main__":
    asyncio.run(main())
