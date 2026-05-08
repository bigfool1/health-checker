from unittest.mock import AsyncMock

import pytest

from health_tracker.graph.edges import route_by_action, route_record_type, route_set_plan_type
from health_tracker.graph.nodes._utils import parse_amount_ml, parse_duration
from health_tracker.graph.nodes.intent import _extract_text, _parse_json, _safe_confidence
from health_tracker.graph.nodes.record import diet as rec_diet
from health_tracker.graph.nodes.record import mood as rec_mood
from health_tracker.graph.nodes.record import sport as rec_sport
from health_tracker.graph.nodes.record import water as rec_water
from health_tracker.graph.nodes.set_plan import water as plan_water
from health_tracker.graph.state import GraphState
from health_tracker.graph.templates import (
    RECORD_REQUIRED,
    SET_PLAN_REQUIRED,
    get_missing_prompt,
    get_plan_prompt,
    get_required_fields,
)
from health_tracker.graph.tools import get_all_records, reset_storage

# ── fixtures ──────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_storage():
    reset_storage()


# ── templates ──────────────────────────────────────────

def test_record_required_fields():
    assert RECORD_REQUIRED["water"] == ["beverage_name", "amount_desc", "time_desc", "date"]
    assert RECORD_REQUIRED["diet"] == ["cuisine_name", "meal_time", "dining_method", "date", "calories"]
    assert RECORD_REQUIRED["sport"] == ["sport_name", "duration_min", "date", "time_desc"]
    assert RECORD_REQUIRED["mood"] == ["mood_label", "mood_text", "date"]


def test_set_plan_required_fields():
    assert SET_PLAN_REQUIRED["water"] == ["target_ml"]
    assert SET_PLAN_REQUIRED["diet"] == ["count"]
    assert SET_PLAN_REQUIRED["sport"] == ["duration_min"]
    assert SET_PLAN_REQUIRED["mood"] == ["count"]


def test_get_required_fields():
    assert get_required_fields("record", "water") == ["beverage_name", "amount_desc", "time_desc", "date"]
    assert get_required_fields("set_plan", "water") == ["target_ml"]
    assert get_required_fields("record", "unknown") == []
    assert get_required_fields("ask", "none") == []


def test_get_missing_prompt():
    assert "喝了" in get_missing_prompt("water", "amount_desc")
    assert "吃了什么" in get_missing_prompt("diet", "cuisine_name")
    assert "运动了多久" in get_missing_prompt("sport", "duration_min") or "分钟" in get_missing_prompt("sport", "duration_min")
    assert "焦虑" in get_missing_prompt("mood", "mood_label") or "心情" in get_missing_prompt("mood", "mood_label")
    # unknown field fallback
    assert "unknown_field" in get_missing_prompt("water", "unknown_field")


def test_get_plan_prompt():
    assert "毫升" in get_plan_prompt("water", "target_ml")
    assert "几次" in get_plan_prompt("diet", "count")
    assert "运动" in get_plan_prompt("sport", "duration_min")


# ── edges (routing) ────────────────────────────────────

def test_route_by_action_record():
    assert route_by_action({"action": "record"}) == "route_record_type"


def test_route_by_action_set_plan():
    assert route_by_action({"action": "set_plan"}) == "route_set_plan_type"


def test_route_by_action_ask():
    assert route_by_action({"action": "ask"}) == "handle_ask"


def test_route_by_action_ambiguous():
    assert route_by_action({"action": "ambiguous"}) == "handle_ambiguous"


def test_route_by_action_default():
    assert route_by_action({}) == "handle_ambiguous"


def test_route_record_type_water():
    assert route_record_type({"type": "water"}) == "record_water"


def test_route_record_type_unknown():
    assert route_record_type({"type": "unknown"}) == "handle_ambiguous"


def test_route_set_plan_type_sport():
    assert route_set_plan_type({"type": "sport"}) == "set_plan_sport"


# ── confidence ─────────────────────────────────────────

def test_safe_confidence_float():
    assert _safe_confidence(0.85) == 0.85

def test_safe_confidence_int():
    assert _safe_confidence(1) == 1.0

def test_safe_confidence_string():
    assert _safe_confidence("0.6") == 0.6

def test_safe_confidence_none():
    assert _safe_confidence(None) is None

def test_safe_confidence_clamp():
    assert _safe_confidence(1.5) == 1.0
    assert _safe_confidence(-0.3) == 0.0

def test_safe_confidence_invalid():
    assert _safe_confidence("nope") is None


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


def test_parse_json_think_tag():
    result = _parse_json('<think>用户想记录喝水</think>\n{"action": "record", "type": "water", "entities": {"beverage_name": "水"}}')
    assert result["action"] == "record"
    assert result["type"] == "water"
    assert result["entities"]["beverage_name"] == "水"


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
    state = {"entities": {"beverage_name": "白开水", "amount_desc": "一杯", "time_desc": "早上"}, "pending_entities": {}}
    result = await rec_water.run(state)
    assert "已记录喝水" in result["response"]
    assert "白开水" in result["response"]
    assert result["missing_fields"] == []
    assert result["pending_entities"] == {}
    assert len(get_all_records()) == 1


@pytest.mark.asyncio
async def test_slot_fill_record_missing_field():
    """Water: missing amount → ask for amount. time_desc + date auto-filled."""
    state = {"entities": {"beverage_name": "咖啡"}, "pending_entities": {}}
    result = await rec_water.run(state)
    assert result["missing_fields"] == ["amount"]
    assert "咖啡" in result["response"] or "多少" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_record_merge_pending(clean_storage):
    """Simulates second turn: pending entities from previous call get merged."""
    state = {
        "entities": {"time_desc": "早上"},
        "pending_entities": {"beverage_name": "咖啡", "amount_desc": "两杯"},
    }
    result = await rec_water.run(state)
    assert result["missing_fields"] == []
    assert "已记录喝水" in result["response"]
    assert "咖啡" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_record_diet():
    """Diet: '午餐' in text gets resolved as meal_time. date auto-filled."""
    state = {"entities": {"cuisine_name": "宫保鸡丁", "dining_method": "午餐"}, "pending_entities": {}}
    result = await rec_diet.run(state)
    # meal_time resolved from '午餐', date auto-filled → complete
    assert result["missing_fields"] == []
    assert "饮食" in result["response"]
    assert "宫保鸡丁" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_record_sport():
    state = {"entities": {"sport_name": "跑步", "duration_min": 30, "total_calories": 300}, "pending_entities": {}}
    result = await rec_sport.run(state)
    assert result["missing_fields"] == []
    assert "运动" in result["response"]
    assert "跑步" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_record_mood():
    """Mood: label present, date auto-filled → complete."""
    state = {"entities": {"mood_label": "开心"}, "pending_entities": {}}
    result = await rec_mood.run(state)
    assert result["missing_fields"] == []
    assert "心情" in result["response"]


# ── slot-filling: set_plan ─────────────────────────────

@pytest.mark.asyncio
async def test_slot_fill_set_plan_complete(clean_storage):
    state = {"entities": {"target_ml": "2000"}, "pending_entities": {}}
    result = await plan_water.run(state)
    assert "2000" in result["response"]
    assert result["missing_fields"] == []


@pytest.mark.asyncio
async def test_slot_fill_set_plan_missing():
    state = {"entities": {}, "pending_entities": {}}
    result = await plan_water.run(state)
    assert "target_ml" in result["missing_fields"]
    assert "毫升" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_set_plan_merge_pending(clean_storage):
    state = {"entities": {"target_ml": "2000"}, "pending_entities": {}}
    result = await plan_water.run(state)
    assert result["missing_fields"] == []
    assert "2000" in result["response"]


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
        "handle_ask", "handle_ambiguous",
        "record_water", "record_diet", "record_sport", "record_mood",
        "set_plan_water", "set_plan_diet", "set_plan_sport", "set_plan_mood",
        "route_record_type", "route_set_plan_type",
    ]
    for name in expected:
        assert name in nodes, f"missing node: {name}"


@pytest.mark.asyncio
async def test_graph_full_record_flow(mock_llm_response):
    """Full graph with mock LLM returning complete entities."""
    from unittest.mock import MagicMock

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
    from unittest.mock import MagicMock

    incomplete_response = MagicMock()
    incomplete_response.content = [{"type": "text", "text": '{"action": "record", "type": "water", "entities": {"beverage_name": "咖啡"}}'}]

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=incomplete_response)

    from health_tracker.graph.builder import build_graph
    graph = build_graph(mock_llm)

    state: GraphState = {
        "user_input": "喝了咖啡",
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
    assert result["missing_fields"] == ["amount"]
    assert "多少" in result["response"]


@pytest.mark.asyncio
async def test_graph_with_mock_llm_ambiguous():
    """Test graph with LLM returning ambiguous action."""
    from unittest.mock import MagicMock

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
    from unittest.mock import MagicMock

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
    assert "30" in result["response"]


# ── confidence downgrade ────────────────────────────────

@pytest.mark.asyncio
async def test_graph_low_confidence_downgraded():
    """LLM returns low confidence → action forced to ambiguous."""
    from unittest.mock import MagicMock

    from health_tracker.graph.builder import build_graph

    low_conf = MagicMock()
    low_conf.content = [{"type": "text", "text": '{"action": "record", "type": "water", "confidence": 0.45, "entities": {"beverage_name": "水"}}'}]

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=low_conf)

    graph = build_graph(mock_llm)
    state: GraphState = {"user_input": "...", "context": "", "action": None, "type": None,
                         "entities": {}, "pending_entities": {}, "missing_fields": [], "response": ""}
    result = await graph.ainvoke(state)
    assert result["action"] == "ambiguous"
    assert result["type"] == "none"


@pytest.mark.asyncio
async def test_graph_high_confidence_unchanged():
    """LLM returns high confidence → action passes through unchanged."""
    from unittest.mock import MagicMock

    from health_tracker.graph.builder import build_graph

    high_conf = MagicMock()
    high_conf.content = [{"type": "text", "text": '{"action": "record", "type": "water", "confidence": 0.85, "entities": {"beverage_name": "水", "amount_desc": "一杯"}}'}]

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=high_conf)

    graph = build_graph(mock_llm)
    state: GraphState = {"user_input": "喝了一杯水", "context": "", "action": None, "type": None,
                         "entities": {}, "pending_entities": {}, "missing_fields": [], "response": ""}
    result = await graph.ainvoke(state)
    assert result["action"] == "record"
    assert result["type"] == "water"


@pytest.mark.asyncio
async def test_graph_no_confidence_not_downgraded():
    """LLM returns no confidence field → backward compatible, not downgraded."""
    from unittest.mock import MagicMock

    from health_tracker.graph.builder import build_graph

    no_conf = MagicMock()
    no_conf.content = [{"type": "text", "text": '{"action": "record", "type": "water", "entities": {"beverage_name": "水", "amount_desc": "一杯"}}'}]

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=no_conf)

    graph = build_graph(mock_llm)
    state: GraphState = {"user_input": "喝了一杯水", "context": "", "action": None, "type": None,
                         "entities": {}, "pending_entities": {}, "missing_fields": [], "response": ""}
    result = await graph.ainvoke(state)
    assert result["action"] == "record"
    assert result["type"] == "water"


# ── session persistence ────────────────────────────────

@pytest.mark.asyncio
async def test_session_cross_turn_slot_filling():
    """Simulate two-turn interaction via direct graph invocation."""
    from unittest.mock import MagicMock

    from health_tracker.graph.builder import build_graph

    # Turn 1: LLM returns partial entities (missing amount)
    turn1_response = MagicMock()
    turn1_response.content = [{"type": "text", "text": '{"action": "record", "type": "water", "entities": {"beverage_name": "咖啡"}}'}]

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=turn1_response)

    graph = build_graph(mock_llm)

    # Turn 1
    state1: GraphState = {
        "user_input": "喝了咖啡",
        "context": "",
        "action": None, "type": None,
        "entities": {}, "pending_entities": {}, "missing_fields": [], "response": "",
    }
    r1 = await graph.ainvoke(state1)
    assert r1["missing_fields"] == ["amount"]
    assert "多少" in r1["response"]

    # Turn 2: LLM returns amount_desc with context about missing field
    turn2_response = MagicMock()
    turn2_response.content = [{"type": "text", "text": '{"action": "record", "type": "water", "entities": {"amount_desc": "两杯"}}'}]

    mock_llm.ainvoke = AsyncMock(return_value=turn2_response)

    state2: GraphState = {
        "user_input": "两杯",
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


# ── edge case: vague entities ───────────────────────────

@pytest.mark.asyncio
async def test_slot_fill_vague_entity_omitted():
    """
    用户说"喝了一杯东西"→ LLM 应省略模糊的 beverage_name
    → entities 只有 amount_desc 和 time_desc
    → slot-fill 追问饮品名。
    """
    state = {"entities": {"amount_desc": "一杯", "time_desc": "刚刚"}, "pending_entities": {}}
    result = await rec_water.run(state)
    assert "beverage_name" in result["missing_fields"]
    assert "饮品" in result["response"]


@pytest.mark.asyncio
async def test_graph_vague_input_triggers_followup():
    """
    端到端：mock LLM 正确省略模糊值，验证 graph 返回追问。
    """
    from unittest.mock import MagicMock

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
async def test_slot_fill_vague_value_filtered():
    """
    即使 LLM 提取了模糊值（如"东西"），per-type slot-fill 也会过滤。
    这是比旧实现更优的行为——代码层做兜底，不依赖 LLM 的 prompt 遵守度。
    """
    state = {"entities": {"beverage_name": "东西", "amount_desc": "一杯", "time_desc": "刚刚"}, "pending_entities": {}}
    result = await rec_water.run(state)
    # "东西" in WATER_GENERIC → filtered out → missing beverage_name
    assert "beverage_name" in result["missing_fields"]
    assert "饮品" in result["response"]


# ── edge case: amount parsing ───────────────────────────

def test_parse_amount_ml_standard():
    assert parse_amount_ml("300ml") == 300
    assert parse_amount_ml("1.5l") == 1500
    assert parse_amount_ml("一杯") == 250
    assert parse_amount_ml("两杯") == 500
    assert parse_amount_ml("半瓶") == 250


def test_parse_amount_ml_unusual():
    assert parse_amount_ml("一大口") is None       # unsupported unit
    assert parse_amount_ml("一点点") is None       # vague
    assert parse_amount_ml("") is None
    assert parse_amount_ml(None) is None           # type: ignore


def test_parse_duration_edge():
    assert parse_duration("半小时") == 30
    assert parse_duration("1小时30分钟") == 90
    assert parse_duration("45") == 45
    assert parse_duration("一个半小时") == 30      # "半小时" substring matched
    assert parse_duration("一会儿") is None        # vague
    assert parse_duration(None) is None


# ── edge case: slot-fill boundaries ─────────────────────

@pytest.mark.asyncio
async def test_slot_fill_water_unusual_amount_triggers_ask():
    """Unparseable amount (一大口) → missing amount → ask."""
    state = {"entities": {"beverage_name": "水", "amount_desc": "一大口"}, "pending_entities": {}}
    result = await rec_water.run(state)
    assert "amount" in result["missing_fields"]
    assert "多少" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_diet_no_meal_hint(clean_storage):
    """No meal_time in entities or combined text → ask for meal_time."""
    state = {"entities": {"cuisine_name": "沙拉"}, "pending_entities": {}}
    result = await rec_diet.run(state)
    assert "meal_time" in result["missing_fields"]
    assert "餐" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_mood_vague_boundary():
    """'还行' in MOOD_VAGUE → filtered → ask."""
    state = {"entities": {"mood_label": "还行"}, "pending_entities": {}}
    result = await rec_mood.run(state)
    assert "mood_label" in result["missing_fields"]
    assert "焦虑" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_set_plan_water_unreasonable():
    """target_ml=99999 → unreasonable → ask again."""
    state = {"entities": {"target_ml": 99999}, "pending_entities": {}}
    result = await plan_water.run(state)
    assert "target_ml" in result["missing_fields"]
    assert "合理" in result["response"]


@pytest.mark.asyncio
async def test_slot_fill_set_plan_water_zero():
    """target_ml=0 → invalid → ask."""
    state = {"entities": {"target_ml": 0}, "pending_entities": {}}
    result = await plan_water.run(state)
    assert "target_ml" in result["missing_fields"]


@pytest.mark.asyncio
async def test_slot_fill_sport_default_calorie():
    """Unrecognized sport → uses default calorie rate (6 kcal/min)."""
    state = {"entities": {"sport_name": "攀岩", "duration_min": 60}, "pending_entities": {}}
    result = await rec_sport.run(state)
    assert result["missing_fields"] == []
    assert "攀岩" in result["response"]
    assert "360" in result["response"]  # 60 * 6
