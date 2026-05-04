from health_tracker.graph.state import GraphState

RECORD_TYPES = {"water", "diet", "sport", "mood", "med"}
SET_PLAN_TYPES = {"water", "diet", "sport", "mood", "med"}


def route_by_action(state: GraphState) -> str:
    action = state.get("action", "ambiguous")
    if action == "record":
        return "route_record_type"
    if action == "set_plan":
        return "route_set_plan_type"
    return f"handle_{action}"


def route_record_type(state: GraphState) -> str:
    record_type = state.get("type", "")
    if record_type in RECORD_TYPES:
        return f"record_{record_type}"
    return "handle_ambiguous"


def route_set_plan_type(state: GraphState) -> str:
    plan_type = state.get("type", "")
    if plan_type in SET_PLAN_TYPES:
        return f"set_plan_{plan_type}"
    return "handle_ambiguous"


ALL_NODES = ["extract_intent"]
ACTION_NODES = ["handle_ask", "handle_ambiguous", "handle_modify_delete"]
RECORD_NODES = [f"record_{t}" for t in RECORD_TYPES]
SET_PLAN_NODES = [f"set_plan_{t}" for t in SET_PLAN_TYPES]
ROUTE_NODES = ["route_record_type", "route_set_plan_type"]
