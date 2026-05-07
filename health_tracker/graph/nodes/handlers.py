from health_tracker.graph.state import GraphState


async def handle_ask(state: GraphState) -> dict:
    return {
        "response": "问答功能开发中，请稍后再试。",
        "pending_entities": {},
    }


async def handle_ambiguous(state: GraphState) -> dict:
    return {
        "response": "抱歉，我不太确定您的意思。您是想记录健康数据（如喝水、饮食、运动、心情），还是想了解健康相关问题？请说得更具体一些。",
        "pending_entities": {},
    }
