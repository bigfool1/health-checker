from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.language_models import BaseChatModel

from health_tracker.graph.state import GraphState
from health_tracker.graph.nodes.intent import extract_intent
from health_tracker.graph.nodes.handlers import handle_ask, handle_ambiguous
from health_tracker.graph.nodes.record import water as rec_water
from health_tracker.graph.nodes.record import diet as rec_diet
from health_tracker.graph.nodes.record import sport as rec_sport
from health_tracker.graph.nodes.record import mood as rec_mood
from health_tracker.graph.nodes.set_plan import water as plan_water
from health_tracker.graph.nodes.set_plan import diet as plan_diet
from health_tracker.graph.nodes.set_plan import sport as plan_sport
from health_tracker.graph.nodes.set_plan import mood as plan_mood
from health_tracker.graph.edges import route_by_action, route_record_type, route_set_plan_type

RECORD_HANDLERS = {
    "water": rec_water.run,
    "diet": rec_diet.run,
    "sport": rec_sport.run,
    "mood": rec_mood.run,
}

SET_PLAN_HANDLERS = {
    "water": plan_water.run,
    "diet": plan_diet.run,
    "sport": plan_sport.run,
    "mood": plan_mood.run,
}

RECORD_TYPES = ["water", "diet", "sport", "mood"]
SET_PLAN_TYPES = ["water", "diet", "sport", "mood"]


def build_graph(llm: BaseChatModel) -> CompiledStateGraph:
    builder = StateGraph(GraphState)

    # intent extraction node
    builder.add_node("extract_intent", _make_intent_node(llm))

    # action handler nodes
    builder.add_node("handle_ask", _make_ask_node(llm))
    builder.add_node("handle_ambiguous", _make_handler(handle_ambiguous))

    # record type nodes (per-type slot-filling)
    for rt in RECORD_TYPES:
        builder.add_node(f"record_{rt}", _make_handler(RECORD_HANDLERS[rt]))

    # set_plan type nodes (per-type slot-filling)
    for pt in SET_PLAN_TYPES:
        builder.add_node(f"set_plan_{pt}", _make_handler(SET_PLAN_HANDLERS[pt]))

    # set entry point
    builder.set_entry_point("extract_intent")

    # action routing from extract_intent
    builder.add_conditional_edges(
        "extract_intent",
        route_by_action,
        {
            "handle_ask": "handle_ask",
            "handle_ambiguous": "handle_ambiguous",
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

    return builder.compile()


def _make_intent_node(llm: BaseChatModel):
    async def node(state: GraphState) -> dict:
        return await extract_intent(state, llm)
    return node


def _make_ask_node(llm: BaseChatModel):
    async def node(state: GraphState) -> dict:
        return await handle_ask(state, llm)
    return node


def _make_handler(fn):
    async def node(state: GraphState) -> dict:
        return await fn(state)
    return node


async def _passthrough(state: GraphState) -> dict:
    return {}
