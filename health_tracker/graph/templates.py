RECORD_REQUIRED: dict[str, list[str]] = {
    "water": ["beverage_name", "amount_desc", "time_desc", "date"],
    "diet": ["cuisine_name", "meal_time", "dining_method", "date", "calories"],
    "sport": ["sport_name", "duration_min", "date", "time_desc"],
    "mood": ["mood_label", "mood_text", "date"],
}

SET_PLAN_REQUIRED: dict[str, list[str]] = {
    "water": ["target_ml"],
    "diet": ["count"],
    "sport": ["duration_min"],
    "mood": ["count"],
}

MISSING_PROMPTS: dict[str, dict[str, str]] = {
    "water": {
        "beverage_name": "喝了什么饮品？咖啡、茶、白水还是其他？",
        "amount_desc": "喝了多少？大概一杯（250ml）、一瓶（500ml）还是其他量？",
        "time_desc": "请问是什么时候喝的？",
        "date": "请问是哪天喝的？",
        "amount": "喝了多少？大概一杯（250ml）、一瓶（500ml）还是其他量？",
    },
    "diet": {
        "cuisine_name": "请问吃了什么？简单描述一下食物名称就好。",
        "meal_time": "这是哪一餐？早餐、午餐、晚餐还是零食？",
        "dining_method": "请问是在家做的还是在外面吃的？",
        "date": "请问是哪天吃的？",
        "calories": "请问大概多少卡路里？",
    },
    "sport": {
        "sport_name": "做了什么运动？跑步、快走、力量训练、瑜伽还是其他？",
        "duration_min": "运动了多长时间？大概几分钟？",
        "date": "请问是哪天运动的？",
        "time_desc": "请问是什么时间运动的？",
    },
    "mood": {
        "mood_label": "能具体说下是感到焦虑、疲惫、沮丧还是其他？想记录为哪种情绪呢？",
        "mood_text": "能多说两句当时的感受吗？",
        "date": "请问是哪天的心情？",
    },
}

PLAN_PROMPTS: dict[str, dict[str, str]] = {
    "water": {
        "target_ml": "你希望每天喝多少毫升水？例如 2000ml。",
    },
    "diet": {
        "count": "你希望每天记录几次饮食？例如 3 次（早午晚）。",
    },
    "sport": {
        "duration_min": "你希望每天运动多久？例如 30 分钟或 1 小时。",
    },
    "mood": {
        "count": "你希望每天记录几次心情？例如 3 次。",
    },
}


def get_required_fields(action: str, record_type: str) -> list[str]:
    if action == "record":
        return RECORD_REQUIRED.get(record_type, [])
    if action == "set_plan":
        return SET_PLAN_REQUIRED.get(record_type, [])
    return []


def get_missing_prompt(record_type: str, field: str) -> str:
    return MISSING_PROMPTS.get(record_type, {}).get(field, f"请提供 {field}")


def get_plan_prompt(record_type: str, field: str) -> str:
    return PLAN_PROMPTS.get(record_type, {}).get(field, f"请提供 {field}")
