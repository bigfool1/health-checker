from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    user_input: str
    context: str
    action: str | None
    type: str | None
    confidence: float | None
    entities: dict[str, Any]
    pending_entities: dict[str, Any]
    missing_fields: list[str]
    response: str
