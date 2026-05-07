import json
import re
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel

from health_tracker.graph.state import GraphState

SYSTEM_PROMPT = """你是一个健康助手的意图识别与参数提取器。

你的任务是从用户输入中识别：
1）action（用户行为类型）
2）type（健康类别）
3）entities（结构化参数）

用户输入可能是口语、省略句或非常简短的表达，请尽量推断合理的健康行为。

只输出 JSON，不要输出解释。

-----------------------------------------------

当前系统时间：
{current_time}

所有时间推断都基于这个时间。

-----------------------------------------------

【action 可选值】

record     用户描述已发生的健康行为（即使实体模糊）
set_plan   用户设置每日目标或计划
ask        用户咨询健康问题
ambiguous  完全无法判断意图

【action 判断优先级】

1. 已发生行为线索（喝了/吃了/跑了/吃了药/刚/今天 + 动作词）→ record
   即使实体模糊（"东西""什么""了点"），也优先判 record，让下游追问
2. 计划意图（每天/目标/计划/提醒我/帮我设置）→ set_plan
3. 咨询意图（怎么/为什么/是否/推荐/多少热量/有没有）→ ask

【type 可选值】
water / diet / sport / mood / none

【模糊词处理】
以下泛词不提取为字段值，对应字段填 null：
东西、饮料、喝的、吃的、啥的、不知道、随便、忘了、不清楚、就那样、还行

-----------------------------------------------

【各 type 的 entities schema】

water：
- beverage_name: 具体饮品名（"咖啡""白水""牛奶"），泛词填 null
- amount_desc: 原始量词（"一杯""300ml""一瓶"），未提则 null
- time_desc: HH:mm，未提则 null（下游填充当前时间）
- date: YYYY-MM-DD，未提则 null（下游填充今天）

diet：
- cuisine_name: 具体食物名（"牛排""沙拉"），减肥食谱/减脂餐等泛主题填 null
- meal_time: breakfast/lunch/dinner/snack 或 null
- dining_method: home_cooked/eat_out 或 null
- date: YYYY-MM-DD，未提则 null
- calories: 数值或 null

sport：
- sport_name: 运动名称
- duration_min: 分钟数（"半小时"→30，"1小时"→60），未提则 null
- date: YYYY-MM-DD，未提则 null
- time_desc: HH:mm，未提则 null

mood：
- mood_label: 心情标签（"开心""焦虑""疲惫"等），仅明确表达时填写，模糊（"不太好"）填 null
- mood_text: 用户原始情绪描述
- date: YYYY-MM-DD，未提则 null

set_plan 时的 entities：
- water → target_ml: 每日喝水目标毫升数
- diet → count: 每天记录次数
- sport → duration_min: 每天运动目标分钟数
- mood → count: 每天记录次数

-----------------------------------------------

【时间解析】
日期：「今天」→ 当前日期，「昨天」→ 当前日期-1天
时间：「早上」→ 08:00，「中午」→ 12:00，「下午」→ 15:00，「晚上」→ 19:00

其余时间推断全部由下游 code 节点处理，不需要在 prompt 中计算。

-----------------------------------------------

【输出 JSON 格式】

{
  "action": "",
  "type": "",
  "confidence": 0-1,
  "entities": {}
}

-----------------------------------------------

【示例】

用户：刚才喝了一杯咖啡

{
  "action":"record",
  "type":"water",
  "confidence":0.95,
  "entities":{
    "beverage_name":"咖啡",
    "amount_desc":"一杯",
    "time_desc":"10:00"
  }
}

--------------------------------

用户：我刚刚喝了一杯东西

{
  "action":"record",
  "type":"water",
  "confidence":0.92,
  "entities":{
    "beverage_name":null,
    "amount_desc":"一杯",
    "time_desc":null
  }
}

--------------------------------

用户：今天午饭吃了牛排，在餐厅

{
  "action":"record",
  "type":"diet",
  "confidence":0.96,
  "entities":{
    "cuisine_name":"牛排",
    "meal_time":"lunch",
    "dining_method":"eat_out"
  }
}

--------------------------------

用户：今天跑步30分钟

{
  "action":"record",
  "type":"sport",
  "confidence":0.97,
  "entities":{
    "sport_name":"跑步",
    "duration_min":30
  }
}

--------------------------------

用户：我今天不太开心

{
  "action":"record",
  "type":"mood",
  "confidence":0.88,
  "entities":{
    "mood_label":null,
    "mood_text":"我不太开心"
  }
}

--------------------------------

用户：每天喝2000ml水

{
  "action":"set_plan",
  "type":"water",
  "confidence":0.97,
  "entities":{
    "target_ml":2000
  }
}

--------------------------------

用户：这道菜多少热量

{
  "action":"ask",
  "type":"none",
  "confidence":0.92,
  "entities":{}
}

--------------------------------

用户：有没有减肥食谱？想20天瘦5斤

{
  "action":"ask",
  "type":"diet",
  "confidence":0.96,
  "entities":{
    "cuisine_name":null
  }
}

请严格只输出 JSON。"""


def _build_prompt() -> str:
    now = datetime.now()
    current_time = f"{now.strftime('%Y-%m-%d %H:%M')}（星期{_weekday_cn(now.weekday())}）"
    return SYSTEM_PROMPT.replace("{current_time}", current_time)


def _weekday_cn(wd: int) -> str:
    return ["一", "二", "三", "四", "五", "六", "日"][wd]


async def extract_intent(state: GraphState, llm: BaseChatModel) -> dict:
    user_input = state.get("user_input", "")
    context = state.get("context", "")

    messages = [SystemMessage(content=_build_prompt())]
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
    if not text:
        return {}
    text = text.strip()

    # handle <think>...</think> tags (DeepSeek V4 Flash tagged reasoning)
    if text.startswith("<think>"):
        end = text.find("</think>")
        if end != -1:
            text = text[end + len("</think>"):].strip()

    # handle ```json ... ``` fences
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        text = m.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # fallback: find outermost JSON object by brace counting
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}
