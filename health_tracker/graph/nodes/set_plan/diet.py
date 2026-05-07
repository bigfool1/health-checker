from health_tracker.graph.state import GraphState
from health_tracker.graph.nodes._utils import safe_int
from health_tracker.graph.tools import save_plan


async def run(state: GraphState) -> dict:
    entities = state.get("entities", {})
    pending = state.get("pending_entities", {})

    count = safe_int(entities.get("count")) or safe_int(pending.get("count"))

    slot_values = {"count": count}

    if count is None or count <= 0:
        return {
            "missing_fields": ["count"],
            "pending_entities": slot_values,
            "response": "你希望每天记录几次饮食？例如 3 次（早午晚）。",
        }

    plan = await save_plan("diet", slot_values)
    return {
        "missing_fields": [],
        "pending_entities": {},
        "response": f"好的，已经帮你设置每天记录 {count} 次饮食。其他健康目标需要我帮你一起设置吗？",
    }
