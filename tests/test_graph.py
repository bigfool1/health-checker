import json
import pytest
from unittest.mock import AsyncMock, patch

from health_tracker.graph.state import GraphState
from health_tracker.graph.templates import (
    RECORD_REQUIRED,
    SET_PLAN_REQUIRED,
    get_required_fields,
    get_missing_prompt,
    get_plan_prompt,
)
from health_tracker.graph.edges import route_by_action, route_record_type, route_set_plan_type
from health_tracker.graph.nodes.slot_fill import slot_fill_record, slot_fill_set_plan
from health_tracker.graph.nodes.intent import _parse_json, _extract_text
from health_tracker.graph.tools import reset_storage, get_all_records


# ── fixtures ──────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_storage():
    reset_storage()


# ── templates ──────────────────────────────────────────

def test_record_required_fields():
    assert RECORD_REQUIRED["water"] == ["beverage_name", "amount_desc", "time_desc"]
    assert RECORD_REQUIRED["diet"] == ["cuisine_name", "date", "dining_method"]
    assert RECORD_REQUIRED["sport"] == ["sport_name", "duration_min", "total_calories"]
    assert RECORD_REQUIRED["mood"] == ["mood_label", "date"]
    assert RECORD_REQUIRED["med"] == ["med_name"]


def test_set_plan_required_fields():
    assert SET_PLAN_REQUIRED["water"] == ["target_ml"]
    assert SET_PLAN_REQUIRED["diet"] == ["count"]
    assert SET_PLAN_REQUIRED["sport"] == ["duration_min"]
    assert SET_PLAN_REQUIRED["mood"] == ["count"]
    assert SET_PLAN_REQUIRED["med"] == ["med_name", "times_per_day"]


def test_get_required_fields():
    assert get_required_fields("record", "water") == ["beverage_name", "amount_desc", "time_desc"]
    assert get_required_fields("set_plan", "water") == ["target_ml"]
    assert get_required_fields("record", "unknown") == []
    assert get_required_fields("ask", "none") == []


def test_get_missing_prompt():
    assert "喝了多少" in get_missing_prompt("water", "amount_desc")
    assert "吃了什么" in get_missing_prompt("diet", "cuisine_name")
    assert "运动了多久" in get_missing_prompt("sport", "duration_min")
    assert "心情如何" in get_missing_prompt("mood", "mood_label")
    assert "药物" in get_missing_prompt("med", "med_name")
    # unknown field fallback
    assert "unknown_field" in get_missing_prompt("water", "unknown_field")


def test_get_plan_prompt():
    assert "毫升" in get_plan_prompt("water", "target_ml")
    assert "次数" in get_plan_prompt("diet", "count")
    assert "时长" in get_plan_prompt("sport", "duration_min")
    assert "几次" in get_plan_prompt("med", "times_per_day")


# ── edges (routing) ────────────────────────────────────

def test_route_by_action_record():
    assert route_by_action({"action": "record"}) == "route_record_type"


def test_route_by_action_set_plan():
    assert route_by_action({"action": "set_plan"}) == "route_set_plan_type"


def test_route_by_action_ask():
    assert route_by_action({"action": "ask"}) == "handle_ask"


def test_route_by_action_ambiguous():
    assert route_by_action({"action": "ambiguous"}) == "handle_ambiguous"


def test_route_by_action_modify_delete():
    assert route_by_action({"action": "modify_delete"}) == "handle_modify_delete"


def test_route_by_action_default():
    assert route_by_action({}) == "handle_ambiguous"


def test_route_record_type_water():
    assert route_record_type({"type": "water"}) == "record_water"


def test_route_record_type_unknown():
    assert route_record_type({"type": "unknown"}) == "handle_ambiguous"


def test_route_set_plan_type_med():
    assert route_set_plan_type({"type": "med"}) == "set_plan_med"


# ── JSON parsing ───────────────────────────────────────

def test_parse_json_plain():
    result = _parse_json('{"action": "record", "type": "water", "entities": {"amount_desc": "一杯"}}')
    assert result["action"] == "record"
    assert result["type"] == "water"
    assert result["entities"]["amount_desc"] == "一杯"


def test_parse_json_with_markdown_fence():
    result = _parse_json('```json\n{"action": "ask", "type": "none", "entities": {}}\n```')
    assert result["action"] == "ask"
    assert result["type"] == "none"


def test_parse_json_nested_in_text():
    result = _parse_json('some text {"action": "ambiguous", "type": "none", "entities": {}} more text')
    assert result["action"] == "ambiguous"


def test_parse_json_invalid_returns_empty():
    result = _parse_json("not json at all")
    assert result == {}


def test_extract_text_from_content_block():
    class FakeResponse:
        content = [{"type": "text", "text": "hello"}]
    assert _extract_text(FakeResponse()) == "hello"


def test_extract_text_from_string_content():
    class FakeResponse:
        content = "plain text"
    assert _extract_text(FakeResponse()) == "plain text"


# ── slot-filling: record ───────────────────────────────

@pytest.mark.asyncio
async def test_slot_fill_record_all_fields_present(clean_storage):
    state = {
        "type": "water",
        "entities": {"beverage_name": "白开水", "amount_desc": "一杯", "time_desc": "早上"},
        "pending_entities": {},
    }
    result = await slot_fill_record(state)
    assert "已记录喝水" in result["response"]
    assert "白开水" in result["response"]
    assert result["missing_fields"] == []
    assert result["pending_entities"] == {}
    assert len(get_all_records()) == 1


@pytest.mark.asyncio
async def test_slot_fill_record_missing_field():
    state = {
        "type": "water",
        "entities": {"beverage_name": "咖啡"},
        "pending_entities": {},
    }
    result = await slot_fill_record(state)
    assert result["missing_fields"] == ["amount_desc", "time_desc"]
    assert "请问" in result["response"]
    assert result["pending_entities"] == {"beverage_name": "咖啡"}


@pytest.mark.asyncio
async def test_slot_fill_record_merge_pending(clean_storage):
    """Simulates second turn: pending entities from previous call get merged."""
    state = {
        "type": "water",
        "entities": {"time_desc": "早上"},
        "pending_entities": {"beverage_name": "咖啡", "amount_desc": "两杯"},
    }
    result = await slot_fill_record(state)
    assert result["missing_fields"] == []
    assert "已记录喝水" in result["response"]
    assert "咖啡" in result["response"]
    assert "早上" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_record_diet():
    state = {
        "type": "diet",
        "entities": {"cuisine_name": "宫保鸡丁", "dining_method": "午餐"},
        "pending_entities": {},
    }
    result = await slot_fill_record(state)
    assert result["missing_fields"] == ["date"]
    assert "哪天" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_record_sport():
    state = {
        "type": "sport",
        "entities": {"sport_name": "跑步", "duration_min": 30, "total_calories": 300},
        "pending_entities": {},
    }
    result = await slot_fill_record(state)
    assert result["missing_fields"] == []
    assert "运动" in result["response"]
    assert "跑步" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_record_mood():
    state = {
        "type": "mood",
        "entities": {"mood_label": "开心"},
        "pending_entities": {},
    }
    result = await slot_fill_record(state)
    assert result["missing_fields"] == ["date"]
    assert "心情" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_record_med():
    state = {
        "type": "med",
        "entities": {"med_name": "阿司匹林"},
        "pending_entities": {},
    }
    result = await slot_fill_record(state)
    assert result["missing_fields"] == []
    assert "用药" in result["response"]
    assert "阿司匹林" in result["response"]


# ── slot-filling: set_plan ─────────────────────────────

@pytest.mark.asyncio
async def test_slot_fill_set_plan_complete(clean_storage):
    state = {
        "type": "water",
        "entities": {"target_ml": "2000"},
        "pending_entities": {},
    }
    result = await slot_fill_set_plan(state)
    assert "已设置" in result["response"]
    assert "2000" in result["response"]
    assert result["missing_fields"] == []


@pytest.mark.asyncio
async def test_slot_fill_set_plan_missing():
    state = {
        "type": "med",
        "entities": {"med_name": "阿司匹林"},
        "pending_entities": {},
    }
    result = await slot_fill_set_plan(state)
    assert "times_per_day" in result["missing_fields"]
    assert "几次" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_set_plan_merge_pending(clean_storage):
    state = {
        "type": "med",
        "entities": {"times_per_day": "3"},
        "pending_entities": {"med_name": "阿司匹林"},
    }
    result = await slot_fill_set_plan(state)
    assert result["missing_fields"] == []
    assert "已设置" in result["response"]


# ── API integration (mock LLM) ─────────────────────────

@pytest.fixture
def mock_llm_response():
    """Returns a fake LLM response object with content blocks."""
    class FakeResponse:
        content = [{"type": "text", "text": '{"action": "record", "type": "water", "entities": {"beverage_name": "水", "amount_desc": "一杯", "time_desc": "今天"}}'}]
    return FakeResponse()


def test_full_graph_structure():
    from langchain_anthropic import ChatAnthropic
    from health_tracker.graph.builder import build_graph

    llm = ChatAnthropic(model="test", api_key="sk-test", base_url="https://test.local")
    graph = build_graph(llm)
    nodes = graph.get_graph().nodes

    expected = [
        "extract_intent",
        "handle_ask", "handle_ambiguous", "handle_modify_delete",
        "record_water", "record_diet", "record_sport", "record_mood", "record_med",
        "set_plan_water", "set_plan_diet", "set_plan_sport", "set_plan_mood", "set_plan_med",
        "route_record_type", "route_set_plan_type",
    ]
    for name in expected:
        assert name in nodes, f"missing node: {name}"


@pytest.mark.asyncio
async def test_graph_full_record_flow(mock_llm_response):
    """Full graph with mock LLM returning complete entities."""
    from unittest.mock import MagicMock, AsyncMock
    from health_tracker.graph.builder import build_graph

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

    graph = build_graph(mock_llm)

    state: GraphState = {
        "user_input": "今天喝了一杯水",
        "context": "",
        "action": None,
        "type": None,
        "entities": {},
        "pending_entities": {},
        "missing_fields": [],
        "response": "",
    }

    result = await graph.ainvoke(state)

    assert result["action"] == "record"
    assert result["type"] == "water"
    assert "已记录喝水" in result["response"]


@pytest.mark.asyncio
async def test_graph_with_mock_llm_missing_field():
    """Test graph with LLM returning incomplete entities."""
    from unittest.mock import MagicMock, AsyncMock

    incomplete_response = MagicMock()
    incomplete_response.content = [{"type": "text", "text": '{"action": "record", "type": "diet", "entities": {"cuisine_name": "米饭", "dining_method": "午餐"}}'}]

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=incomplete_response)

    from health_tracker.graph.builder import build_graph
    graph = build_graph(mock_llm)

    state: GraphState = {
        "user_input": "中午吃了米饭",
        "context": "",
        "action": None,
        "type": None,
        "entities": {},
        "pending_entities": {},
        "missing_fields": [],
        "response": "",
    }

    result = await graph.ainvoke(state)
    assert result["action"] == "record"
    assert result["type"] == "diet"
    assert result["missing_fields"] == ["date"]
    assert "哪天" in result["response"]


@pytest.mark.asyncio
async def test_graph_with_mock_llm_ambiguous():
    """Test graph with LLM returning ambiguous action."""
    from unittest.mock import MagicMock, AsyncMock

    ambig_response = MagicMock()
    ambig_response.content = [{"type": "text", "text": '{"action": "ambiguous", "type": "none", "entities": {}}'}]

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=ambig_response)

    from health_tracker.graph.builder import build_graph
    graph = build_graph(mock_llm)

    state: GraphState = {
        "user_input": "嗯",
        "context": "",
        "action": None,
        "type": None,
        "entities": {},
        "pending_entities": {},
        "missing_fields": [],
        "response": "",
    }

    result = await graph.ainvoke(state)
    assert result["action"] == "ambiguous"
    assert "不太确定" in result["response"]


@pytest.mark.asyncio
async def test_graph_with_mock_llm_set_plan():
    """Test graph with LLM returning set_plan action."""
    from unittest.mock import MagicMock, AsyncMock

    plan_response = MagicMock()
    plan_response.content = [{"type": "text", "text": '{"action": "set_plan", "type": "sport", "entities": {"duration_min": 30}}'}]

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=plan_response)

    from health_tracker.graph.builder import build_graph
    graph = build_graph(mock_llm)

    state: GraphState = {
        "user_input": "设置每天运动30分钟",
        "context": "",
        "action": None,
        "type": None,
        "entities": {},
        "pending_entities": {},
        "missing_fields": [],
        "response": "",
    }

    result = await graph.ainvoke(state)
    assert result["action"] == "set_plan"
    assert result["type"] == "sport"
    assert "已设置" in result["response"]


# ── session persistence ────────────────────────────────

@pytest.mark.asyncio
async def test_session_cross_turn_slot_filling():
    """Simulate two-turn interaction via direct graph invocation."""
    from unittest.mock import MagicMock, AsyncMock
    from health_tracker.graph.builder import build_graph

    # Turn 1: LLM returns partial entities (missing time_desc)
    turn1_response = MagicMock()
    turn1_response.content = [{"type": "text", "text": '{"action": "record", "type": "water", "entities": {"beverage_name": "咖啡", "amount_desc": "一杯"}}'}]

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=turn1_response)

    graph = build_graph(mock_llm)

    # Turn 1
    state1: GraphState = {
        "user_input": "喝了一杯咖啡",
        "context": "",
        "action": None, "type": None,
        "entities": {}, "pending_entities": {}, "missing_fields": [], "response": "",
    }
    r1 = await graph.ainvoke(state1)
    assert r1["missing_fields"] == ["time_desc"]
    assert "什么时候" in r1["response"]

    # Turn 2: LLM returns time_desc with context about missing field
    turn2_response = MagicMock()
    turn2_response.content = [{"type": "text", "text": '{"action": "record", "type": "water", "entities": {"time_desc": "早上"}}'}]

    mock_llm.ainvoke = AsyncMock(return_value=turn2_response)

    state2: GraphState = {
        "user_input": "早上",
        "context": "",
        "action": None, "type": None,
        "entities": {},
        "pending_entities": r1["pending_entities"],  # carried over from turn 1
        "missing_fields": [], "response": "",
    }
    r2 = await graph.ainvoke(state2)
    assert r2["missing_fields"] == []
    assert "已记录喝水" in r2["response"]
    assert "咖啡" in r2["response"]
    assert "早上" in r2["response"]


# ── edge case: vague entities ───────────────────────────

@pytest.mark.asyncio
async def test_slot_fill_vague_entity_omitted():
    """
    用户说"喝了一杯东西"→ LLM 应省略模糊的 beverage_name
    → entities 只有 amount_desc 和 time_desc
    → slot-fill 追问饮品名。
    """
    state = {
        "type": "water",
        "entities": {"amount_desc": "一杯", "time_desc": "刚刚"},
        "pending_entities": {},
    }
    result = await slot_fill_record(state)
    assert "beverage_name" in result["missing_fields"]
    assert "饮品" in result["response"]


@pytest.mark.asyncio
async def test_graph_vague_input_triggers_followup():
    """
    端到端：mock LLM 正确省略模糊值，验证 graph 返回追问。
    """
    from unittest.mock import MagicMock, AsyncMock
    from health_tracker.graph.builder import build_graph

    # LLM 正确地将"东西"省略，只提取了 amount_desc 和 time_desc
    vague_response = MagicMock()
    vague_response.content = [{"type": "text", "text": '{"action": "record", "type": "water", "entities": {"amount_desc": "一杯", "time_desc": "刚刚"}}'}]

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=vague_response)

    graph = build_graph(mock_llm)

    state: GraphState = {
        "user_input": "我刚刚喝了一杯东西",
        "context": "",
        "action": None, "type": None,
        "entities": {}, "pending_entities": {}, "missing_fields": [], "response": "",
    }

    result = await graph.ainvoke(state)
    assert result["action"] == "record"
    assert result["type"] == "water"
    assert "beverage_name" in result["missing_fields"]
    assert "饮品" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_writes_vague_value_as_is():
    """
    已知边界：如果 LLM 没遵守 prompt 指令，仍提取了模糊值（如"东西"），
    slot-fill 会原样写入。因为 slot-fill 只做存在性检查，不做语义质量判断。
    这个测试记录当前行为，不是 bug——修复点在 prompt。
    """
    state = {
        "type": "water",
        "entities": {"beverage_name": "东西", "amount_desc": "一杯", "time_desc": "刚刚"},
        "pending_entities": {},
    }
    result = await slot_fill_record(state)
    assert result["missing_fields"] == []
    assert "东西" in result["response"]
