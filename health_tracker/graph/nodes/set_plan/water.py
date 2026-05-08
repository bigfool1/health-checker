from health_tracker.graph.nodes._utils import safe_int
from health_tracker.graph.state import GraphState
from health_tracker.graph.tools import save_plan


async def run(state: GraphState) -> dict:
    entities = state.get("entities", {})
    pending = state.get("pending_entities", {})

    target_ml = safe_int(entities.get("target_ml")) or safe_int(pending.get("target_ml"))

    slot_values = {"target_ml": target_ml}

    if target_ml is None or target_ml <= 0:
        return {
            "missing_fields": ["target_ml"],
            "pending_entities": slot_values,
            "response": "你希望每天喝多少毫升水？例如 2000ml。",
        }
    if target_ml > 50000:
        return {
            "missing_fields": ["target_ml"],
            "pending_entities": slot_values,
            "response": "这个数值似乎不太合理，请确认一下每天的实际饮水目标（毫升）？",
        }

    await save_plan("water", slot_values)
    return {
        "missing_fields": [],
        "pending_entities": {},
        "response": f"好的，已经帮你设置每天喝 {target_ml}ml 水。其他健康目标需要我帮你一起设置吗？",
    }
