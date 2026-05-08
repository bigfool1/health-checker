from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from health_tracker.graph.state import GraphState

ASK_SYSTEM_PROMPT = """你是一个健康助手。用户正在咨询健康相关问题，请用简洁友好的方式回答。

注意：
- 如果问题与健康无关，礼貌地引导用户回到健康话题
- 不要给出极端的饮食建议或医疗诊断建议
- 如果涉及医疗诊断，提醒用户咨询专业医生"""


async def handle_ask(state: GraphState, llm: BaseChatModel) -> dict:
    user_input = state.get("user_input", "")
    response = await llm.ainvoke([
        SystemMessage(content=ASK_SYSTEM_PROMPT),
        HumanMessage(content=user_input),
    ])
    text = _extract_text(response)
    return {
        "response": text,
        "pending_entities": {},
    }


async def handle_ambiguous(state: GraphState) -> dict:
    return {
        "response": "抱歉，我不太确定您的意思。您是想记录健康数据（如喝水、饮食、运动、心情），还是想了解健康相关问题？请说得更具体一些。",
        "pending_entities": {},
    }


def _extract_text(response) -> str:
    if hasattr(response, "content"):
        content = response.content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "".join(parts)
        return str(content)
    return str(response)
