from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.language_models import BaseChatModel

from health_tracker.graph.state import GraphState
from health_tracker.graph.nodes.intent import extract_intent
from health_tracker.graph.nodes.handlers import handle_ask, handle_ambiguous, handle_modify_delete
from health_tracker.graph.nodes.slot_fill import slot_fill_record, slot_fill_set_plan
from health_tracker.graph.edges import route_by_action, route_record_type, route_set_plan_type

RECORD_TYPES = ["water", "diet", "sport", "mood", "med"]
SET_PLAN_TYPES = ["water", "diet", "sport", "mood", "med"]


def build_graph(llm: BaseChatModel) -> CompiledStateGraph:
    builder = StateGraph(GraphState)

    # intent extraction node
    builder.add_node("extract_intent", _make_intent_node(llm))

    # action handler nodes
    builder.add_node("handle_ask", _make_handler(handle_ask))
    builder.add_node("handle_ambiguous", _make_handler(handle_ambiguous))
    builder.add_node("handle_modify_delete", _make_handler(handle_modify_delete))

    # record type nodes (slot-filling)
    for rt in RECORD_TYPES:
        builder.add_node(f"record_{rt}", _make_handler(slot_fill_record))

    # set_plan type nodes (slot-filling, pass action)
    for pt in SET_PLAN_TYPES:
        builder.add_node(f"set_plan_{pt}", _make_handler(slot_fill_set_plan))

    # set entry point
    builder.set_entry_point("extract_intent")

    # action routing from extract_intent
    builder.add_conditional_edges(
        "extract_intent",
        route_by_action,
        {
            "handle_ask": "handle_ask",
            "handle_ambiguous": "handle_ambiguous",
            "handle_modify_delete": "handle_modify_delete",
            "route_record_type": "route_record_type",
            "route_set_plan_type": "route_set_plan_type",
        },
    )

    # type routing (record)
    builder.add_node("route_record_type", _passthrough)
    builder.add_conditional_edges(
        "route_record_type",
        route_record_type,
        {f"record_{rt}": f"record_{rt}" for rt in RECORD_TYPES}
        | {"handle_ambiguous": "handle_ambiguous"},
    )

    # type routing (set_plan)
    builder.add_node("route_set_plan_type", _passthrough)
    builder.add_conditional_edges(
        "route_set_plan_type",
        route_set_plan_type,
        {f"set_plan_{pt}": f"set_plan_{pt}" for pt in SET_PLAN_TYPES}
        | {"handle_ambiguous": "handle_ambiguous"},
    )

    # all leaf nodes → END
    for rt in RECORD_TYPES:
        builder.add_edge(f"record_{rt}", END)
    for pt in SET_PLAN_TYPES:
        builder.add_edge(f"set_plan_{pt}", END)
    builder.add_edge("handle_ask", END)
    builder.add_edge("handle_ambiguous", END)
    builder.add_edge("handle_modify_delete", END)

    return builder.compile()


def _make_intent_node(llm: BaseChatModel):
    async def node(state: GraphState) -> dict:
        return await extract_intent(state, llm)
    return node


def _make_handler(fn):
    async def node(state: GraphState) -> dict:
        return await fn(state)
    return node


async def _passthrough(state: GraphState) -> dict:
    return {}
