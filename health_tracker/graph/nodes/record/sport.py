from health_tracker.graph.state import GraphState
from health_tracker.graph.nodes._utils import (
    today, current_hhmm, parse_duration, safe_float, format_record_confirm,
)
from health_tracker.graph.tools import save_record

CALORIE_RATE = {
    "跑步": 10, "走路": 4, "快走": 5, "骑车": 8, "游泳": 9,
    "健身": 6, "力量训练": 6, "瑜伽": 4, "打球": 7,
}


async def run(state: GraphState) -> dict:
    entities = state.get("entities", {})
    pending = state.get("pending_entities", {})

    sport_name = entities.get("sport_name") or pending.get("sport_name") or ""
    sport_name = sport_name.strip()
    duration_min = parse_duration(
        entities.get("duration_min") if entities.get("duration_min") is not None
        else pending.get("duration_min")
    )
    distance_km = safe_float(entities.get("distance_km")) or safe_float(pending.get("distance_km"))
    date = entities.get("date") or pending.get("date") or today()
    time_desc = entities.get("time_desc") or pending.get("time_desc") or current_hhmm()

    total_calories = None
    if duration_min is not None:
        rate = CALORIE_RATE.get(sport_name, 6) if sport_name else 6
        total_calories = duration_min * rate

    slot_values = {
        "sport_name": sport_name if sport_name else None,
        "duration_min": duration_min,
        "total_calories": total_calories,
        "distance_km": distance_km if distance_km is not None else None,
        "date": date,
        "time_desc": time_desc,
    }

    if not slot_values["sport_name"]:
        return {
            "missing_fields": ["sport_name"],
            "pending_entities": slot_values,
            "response": "做了什么运动？跑步、快走、力量训练、瑜伽还是其他？",
        }
    if duration_min is None:
        return {
            "missing_fields": ["duration_min"],
            "pending_entities": slot_values,
            "response": "运动了多长时间？大概几分钟？",
        }

    record = await save_record("sport", slot_values)
    return {
        "missing_fields": [],
        "pending_entities": {},
        "response": format_record_confirm("sport", slot_values, record["id"]),
    }
