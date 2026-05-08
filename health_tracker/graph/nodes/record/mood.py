from health_tracker.graph.nodes._utils import format_record_confirm, today
from health_tracker.graph.state import GraphState
from health_tracker.graph.tools import save_record

MOOD_VAGUE = {
    "不太好", "有点烦", "不好", "不太好说", "说不清楚", "不知道",
    "不舒服", "一般", "还行", "凑合", "就那样",
}


async def run(state: GraphState) -> dict:
    entities = state.get("entities", {})
    pending = state.get("pending_entities", {})

    mood_label = entities.get("mood_label") or pending.get("mood_label") or ""
    mood_label = mood_label.strip()
    mood_text = entities.get("mood_text") or pending.get("mood_text") or ""
    date = entities.get("date") or pending.get("date") or today()

    slot_values = {
        "mood_label": mood_label if mood_label and mood_label not in MOOD_VAGUE else None,
        "mood_text": mood_text if mood_text else None,
        "date": date,
    }

    if not slot_values["mood_label"]:
        return {
            "missing_fields": ["mood_label"],
            "pending_entities": slot_values,
            "response": "能具体说下是感到焦虑、疲惫、沮丧还是其他？想记录为哪种情绪呢？",
        }

    record = await save_record("mood", slot_values)
    return {
        "missing_fields": [],
        "pending_entities": {},
        "response": format_record_confirm("mood", slot_values, record["id"]),
    }
