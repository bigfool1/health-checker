import re
from datetime import datetime


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def current_hhmm() -> str:
    return datetime.now().strftime("%H:%M")


def safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_amount_ml(raw: str) -> int | None:
    """一杯→250, 一瓶→500, 300ml→300, 2杯→500."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip().lower().replace(" ", "")
    if raw.endswith("ml"):
        try:
            return int(raw[:-2])
        except ValueError:
            pass
    if raw.endswith("l"):
        try:
            return int(float(raw[:-1]) * 1000)
        except ValueError:
            pass
    mapping = {
        "一杯": 250, "1杯": 250, "一瓶": 500, "1瓶": 500,
        "一桶": 1250, "1桶": 1250, "半杯": 125, "半瓶": 250,
        "两杯": 500, "2杯": 500, "两瓶": 1000, "2瓶": 1000,
        "三杯": 750, "3杯": 750,
    }
    if raw in mapping:
        return mapping[raw]
    for unit, ml_per in [("杯", 250), ("瓶", 500), ("桶", 1250)]:
        if raw.endswith(unit):
            try:
                return int(raw[:-len(unit)]) * ml_per
            except ValueError:
                pass
    return None


def parse_duration(val) -> int | None:
    """半小时→30, 1小时→60, 1小时30分钟→90, 45→45."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    raw = str(val).strip().lower().replace(" ", "")
    if not raw:
        return None
    total = 0
    h_match = re.search(r"(\d+)小时", raw)
    m_match = re.search(r"(\d+)分钟", raw)
    if "半小时" in raw:
        total += 30
    if h_match:
        total += int(h_match.group(1)) * 60
    if m_match:
        total += int(m_match.group(1))
    if total > 0:
        return total
    try:
        return int(raw)
    except ValueError:
        return None


TYPE_LABELS = {
    "water": "喝水",
    "diet": "饮食",
    "sport": "运动",
    "mood": "心情",
}

PLAN_LABELS = {
    "water": "喝水目标",
    "diet": "饮食记录目标",
    "sport": "运动目标",
    "mood": "心情记录目标",
}


def format_record_confirm(record_type: str, entities: dict, record_id: int) -> str:
    label = TYPE_LABELS.get(record_type, record_type)
    detail_parts = []
    for k, v in entities.items():
        if v is not None:
            detail_parts.append(str(v))
    detail = "，".join(detail_parts)
    return f"已记录{label}：{detail}（ID: {record_id}）"


def format_plan_confirm(plan_type: str, entities: dict, plan_id: int) -> str:
    label = PLAN_LABELS.get(plan_type, plan_type)
    detail_parts = []
    for k, v in entities.items():
        if v is not None:
            detail_parts.append(str(v))
    detail = "，".join(detail_parts)
    return f"已设置{label}：{detail}（ID: {plan_id}）"
