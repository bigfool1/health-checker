from health_tracker.graph.state import GraphState
from health_tracker.graph.nodes._utils import parse_duration
from health_tracker.graph.tools import save_plan


async def run(state: GraphState) -> dict:
    entities = state.get("entities", {})
    pending = state.get("pending_entities", {})

    duration_min = parse_duration(
        entities.get("duration_min") if entities.get("duration_min") is not None
        else pending.get("duration_min")
    )

    slot_values = {"duration_min": duration_min}

    if duration_min is None or duration_min <= 0:
        return {
            "missing_fields": ["duration_min"],
            "pending_entities": slot_values,
            "response": "你希望每天运动多久？例如 30 分钟或 1 小时。",
        }

    plan = await save_plan("sport", slot_values)
    return {
        "missing_fields": [],
        "pending_entities": {},
        "response": f"好的，已经帮你设置每天运动 {duration_min} 分钟。其他健康目标需要我帮你一起设置吗？",
    }
