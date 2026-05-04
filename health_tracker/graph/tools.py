import json
from typing import Any

# mock storage for demo
_storage: list[dict[str, Any]] = []


async def save_record(record_type: str, entities: dict[str, Any]) -> dict[str, Any]:
    record = {"id": len(_storage) + 1, "type": record_type, "data": entities}
    _storage.append(record)
    return record


async def save_plan(plan_type: str, entities: dict[str, Any]) -> dict[str, Any]:
    record = {"id": len(_storage) + 1, "type": f"plan_{plan_type}", "data": entities}
    _storage.append(record)
    return record


def get_all_records() -> list[dict[str, Any]]:
    return list(_storage)


def reset_storage() -> None:
    _storage.clear()
