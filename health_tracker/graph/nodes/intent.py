import json

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel

from health_tracker.graph.state import GraphState

SYSTEM_PROMPT = """你是一个健康助手，负责从用户的自然语言输入中提取结构化信息。

输出一个 JSON 对象，包含以下字段：
- action: 用户意图，可选值 "record" | "set_plan" | "modify_delete" | "ask" | "ambiguous"
- type: 健康类型，可选值 "water" | "diet" | "sport" | "mood" | "med" | "none"
- entities: 从输入中提取的参数字典

各 type 对应的 entities 字段：

water → beverage_name, amount_desc, time_desc
  例："喝了一杯水" → {"beverage_name": "水", "amount_desc": "一杯"}

diet → cuisine_name, date, dining_method
  例："中午吃了米饭" → {"cuisine_name": "米饭", "dining_method": "午餐"}

sport → sport_name, duration_min, total_calories
  例："跑步30分钟消耗了300卡" → {"sport_name": "跑步", "duration_min": 30, "total_calories": 300}

mood → mood_label, date
  例："今天很开心" → {"mood_label": "开心"}

med → med_name
  例："吃了阿司匹林" → {"med_name": "阿司匹林"}

set_plan 时的 entities：
  water → target_ml
  diet → count
  sport → duration_min
  mood → count
  med → med_name, times_per_day

只提取具体明确的信息。如果用户使用了模糊词汇（如"东西""喝的""吃的""不知道""随便""忘了"），不要将其作为字段值提取，直接省略该字段。
直接输出 JSON，不要包含其他文字。"""


async def extract_intent(state: GraphState, llm: BaseChatModel) -> dict:
    user_input = state.get("user_input", "")
    context = state.get("context", "")

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    if context:
        messages.append(HumanMessage(content=context))
    messages.append(HumanMessage(content=user_input))

    response = await llm.ainvoke(messages)

    content = _extract_text(response)
    result = _parse_json(content)

    return {
        "action": result.get("action", "ambiguous"),
        "type": result.get("type", "none"),
        "entities": result.get("entities", {}),
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


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[: text.rfind("```")].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        return {}
