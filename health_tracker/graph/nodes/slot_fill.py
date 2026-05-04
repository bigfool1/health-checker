from health_tracker.graph.state import GraphState
from health_tracker.graph.templates import (
    get_required_fields,
    get_missing_prompt,
    get_plan_prompt,
)
from health_tracker.graph.tools import save_record, save_plan


async def slot_fill_record(state: GraphState) -> dict:
    record_type = state.get("type", "")
    entities = state.get("entities", {})
    pending = state.get("pending_entities", {})

    merged = {**pending, **entities}
    required = get_required_fields("record", record_type)
    missing = [f for f in required if f not in merged or not merged[f]]

    if missing:
        field = missing[0]
        prompt = get_missing_prompt(record_type, field)
        return {
            "missing_fields": missing,
            "pending_entities": merged,
            "response": prompt,
        }

    # all fields complete — mock save
    record = await save_record(record_type, merged)
    return {
        "missing_fields": [],
        "pending_entities": {},
        "response": _format_record_confirm(record_type, merged, record["id"]),
    }


async def slot_fill_set_plan(state: GraphState) -> dict:
    plan_type = state.get("type", "")
    entities = state.get("entities", {})
    pending = state.get("pending_entities", {})

    merged = {**pending, **entities}
    required = get_required_fields("set_plan", plan_type)
    missing = [f for f in required if f not in merged or not merged[f]]

    if missing:
        field = missing[0]
        prompt = get_plan_prompt(plan_type, field)
        return {
            "missing_fields": missing,
            "pending_entities": merged,
            "response": prompt,
        }

    # all fields complete — mock save
    plan = await save_plan(plan_type, merged)
    return {
        "missing_fields": [],
        "pending_entities": {},
        "response": _format_plan_confirm(plan_type, merged, plan["id"]),
    }


def _format_record_confirm(record_type: str, entities: dict, record_id: int) -> str:
    type_labels = {
        "water": "喝水",
        "diet": "饮食",
        "sport": "运动",
        "mood": "心情",
        "med": "用药",
    }
    label = type_labels.get(record_type, record_type)

    detail_parts = []
    for k, v in entities.items():
        detail_parts.append(f"{v}")
    detail = "，".join(detail_parts)

    return f"已记录{label}：{detail}（ID: {record_id}）"


def _format_plan_confirm(plan_type: str, entities: dict, plan_id: int) -> str:
    type_labels = {
        "water": "喝水目标",
        "diet": "饮食记录目标",
        "sport": "运动目标",
        "mood": "心情记录目标",
        "med": "用药目标",
    }
    label = type_labels.get(plan_type, plan_type)

    detail_parts = []
    for k, v in entities.items():
        detail_parts.append(f"{v}")
    detail = "，".join(detail_parts)

    return f"已设置{label}：{detail}（ID: {plan_id}）"
