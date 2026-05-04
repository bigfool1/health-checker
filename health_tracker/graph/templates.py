RECORD_REQUIRED: dict[str, list[str]] = {
    "water": ["beverage_name", "amount_desc", "time_desc"],
    "diet": ["cuisine_name", "date", "dining_method"],
    "sport": ["sport_name", "duration_min", "total_calories"],
    "mood": ["mood_label", "date"],
    "med": ["med_name"],
}

SET_PLAN_REQUIRED: dict[str, list[str]] = {
    "water": ["target_ml"],
    "diet": ["count"],
    "sport": ["duration_min"],
    "mood": ["count"],
    "med": ["med_name", "times_per_day"],
}

MISSING_PROMPTS: dict[str, dict[str, str]] = {
    "water": {
        "beverage_name": "请问喝了什么饮品？",
        "amount_desc": "请问喝了多少？",
        "time_desc": "请问是什么时候喝的？",
    },
    "diet": {
        "cuisine_name": "请问吃了什么？",
        "date": "请问是哪天吃的？",
        "dining_method": "请问是早餐、午餐还是晚餐？",
    },
    "sport": {
        "sport_name": "请问做了什么运动？",
        "duration_min": "请问运动了多久（分钟）？",
        "total_calories": "请问消耗了多少卡路里？",
    },
    "mood": {
        "mood_label": "请问心情如何？（开心/平静/焦虑/低落/生气）",
        "date": "请问是哪天的心情？",
    },
    "med": {
        "med_name": "请问服用了什么药物？",
    },
}

PLAN_PROMPTS: dict[str, dict[str, str]] = {
    "water": {
        "target_ml": "请问每日饮水目标是多少毫升？",
    },
    "diet": {
        "count": "请问每日饮食记录次数目标是多少？",
    },
    "sport": {
        "duration_min": "请问每日运动时长目标是多少分钟？",
    },
    "mood": {
        "count": "请问每日心情记录次数目标是多少？",
    },
    "med": {
        "med_name": "请问需要服用什么药物？",
        "times_per_day": "请问每天服用几次？",
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
