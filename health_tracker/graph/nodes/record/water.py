from health_tracker.graph.nodes._utils import (
    current_hhmm,
    format_record_confirm,
    parse_amount_ml,
    today,
)
from health_tracker.graph.state import GraphState
from health_tracker.graph.tools import save_record

WATER_GENERIC = {"东西", "饮料", "喝了点", "啥的", "喝的", "不清楚", "不知道", "随便", "忘了"}


async def run(state: GraphState) -> dict:
    entities = state.get("entities", {})
    pending = state.get("pending_entities", {})

    raw_name = entities.get("beverage_name") or pending.get("beverage_name") or ""
    raw_name = raw_name.strip()
    amount_raw = entities.get("amount_desc") or pending.get("amount_desc") or ""
    amount_ml = parse_amount_ml(str(amount_raw)) if amount_raw else None
    time_desc = entities.get("time_desc") or pending.get("time_desc") or current_hhmm()
    date = entities.get("date") or pending.get("date") or today()

    slot_values = {
        "beverage_name": raw_name if raw_name and raw_name not in WATER_GENERIC else None,
        "amount_desc": str(amount_raw) if amount_raw else None,
        "amount_ml": amount_ml,
        "time_desc": time_desc,
        "date": date,
    }

    missing = []
    if not slot_values["beverage_name"]:
        missing.append("beverage_name")
    if amount_ml is None:
        missing.append("amount")

    if missing:
        if len(missing) >= 2:
            ask = "请问喝了什么饮品？大概多少量？"
        elif missing[0] == "beverage_name":
            ask = "喝了什么饮品？咖啡、茶、白水还是其他？"
        else:
            ask = "喝了多少？大概一杯（250ml）、一瓶（500ml）还是其他量？"
        return {
            "missing_fields": missing,
            "pending_entities": slot_values,
            "response": ask,
        }

    record = await save_record("water", slot_values)
    return {
        "missing_fields": [],
        "pending_entities": {},
        "response": format_record_confirm("water", slot_values, record["id"]),
    }
