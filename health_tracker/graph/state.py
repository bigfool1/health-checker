from typing import TypedDict, Optional, Any


class GraphState(TypedDict, total=False):
    user_input: str
    context: str
    action: Optional[str]
    type: Optional[str]
    entities: dict[str, Any]
    pending_entities: dict[str, Any]
    missing_fields: list[str]
    response: str
