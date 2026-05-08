from health_tracker.graph.nodes._utils import format_record_confirm, safe_int, today
from health_tracker.graph.state import GraphState
from health_tracker.graph.tools import save_record

MEAL_MAP = {
    "早餐": "breakfast", "早饭": "breakfast", "早上": "breakfast",
    "午饭": "lunch", "午餐": "lunch", "中午": "lunch",
    "晚饭": "dinner", "晚餐": "dinner", "晚上": "dinner",
    "宵夜": "snack", "夜宵": "snack", "零食": "snack",
    "下午茶": "snack", "加餐": "snack",
}
DINING_MAP = {
    "自己做": "home_cooked", "在家": "home_cooked", "自己煮": "home_cooked",
    "餐厅": "eat_out", "外面": "eat_out", "下馆子": "eat_out",
    "饭店": "eat_out", "外卖": "eat_out",
}
DIET_GENERIC = {"减肥食谱", "减脂餐", "饮食建议", "怎么吃", "健康餐", "不知道", "随便", "忘了"}


async def run(state: GraphState) -> dict:
    entities = state.get("entities", {})
    pending = state.get("pending_entities", {})

    raw_name = entities.get("cuisine_name") or pending.get("cuisine_name") or ""
    raw_name = raw_name.strip()
    date = entities.get("date") or pending.get("date") or today()
    meal_time = _resolve_meal_time(entities) or pending.get("meal_time", "")
    dining_method = _resolve_dining_method(entities) or pending.get("dining_method", "")
    calories = safe_int(entities.get("calories")) or safe_int(pending.get("calories"))

    slot_values = {
        "cuisine_name": raw_name if raw_name and raw_name not in DIET_GENERIC else None,
        "meal_time": meal_time if meal_time else None,
        "dining_method": dining_method if dining_method else None,
        "calories": calories,
        "date": date,
    }

    missing = []
    if not slot_values["cuisine_name"]:
        missing.append("cuisine_name")
    if not slot_values["meal_time"]:
        missing.append("meal_time")

    if missing:
        if missing[0] == "cuisine_name":
            ask = "请问吃了什么？简单描述一下食物名称就好。"
        else:
            ask = "这是哪一餐？早餐、午餐、晚餐还是零食？"
        return {
            "missing_fields": missing,
            "pending_entities": slot_values,
            "response": ask,
        }

    record = await save_record("diet", slot_values)
    return {
        "missing_fields": [],
        "pending_entities": {},
        "response": format_record_confirm("diet", slot_values, record["id"]),
    }


def _resolve_meal_time(entities: dict) -> str | None:
    raw = entities.get("meal_time") or ""
    if raw in MEAL_MAP:
        return MEAL_MAP[raw]
    if raw in ("breakfast", "lunch", "dinner", "snack"):
        return raw
    combined = " ".join(str(v) for v in entities.values() if isinstance(v, str))
    for keyword, mapped in MEAL_MAP.items():
        if keyword in combined:
            return mapped
    return None


def _resolve_dining_method(entities: dict) -> str | None:
    raw = entities.get("dining_method") or ""
    if raw in ("home_cooked", "eat_out"):
        return raw
    combined = " ".join(str(v) for v in entities.values() if isinstance(v, str))
    for keyword, mapped in DINING_MAP.items():
        if keyword in combined:
            return mapped
    return None
