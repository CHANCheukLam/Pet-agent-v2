from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

from schemas import (
    FeatureIdEnum,
    RouterOutput,
    StageEnum,
    StructuredTaskStubJson,
    ToolInvocationDecision,
)
from validator import (
    should_invoke_planner,
    validate_feature_fields,
)

# =========================================================
# Keyword dictionaries
# =========================================================

TRANSPORT_KEYWORDS = {
    "walk": ["walk", "walking", "步行"],
    "taxi": ["taxi", "cab", "打车", "出租车"],
    "private_car": ["drive", "driving", "self-driving", "self driving", "car", "自驾", "开车", "私家车"],
    "shared_bike": ["bike", "shared bike", "cycling", "骑车", "共享单车"],
    "public_transport": ["metro", "subway", "bus", "public transport", "mtr", "地铁", "公交", "公共交通"],
    "high_speed_rail": ["high speed rail", "high-speed rail", "hsr", "bullet train", "高铁"],
    "rail": ["train", "rail", "火车", "铁路"],
    "flight": ["flight", "plane", "airplane", "飞机", "航班"],
}

DOCUMENT_KEYWORDS = [
    "document", "documents", "checklist", "materials",
    "certificate", "vaccination",
    "证件", "材料", "证明", "疫苗", "检疫",
]

SCENIC_KEYWORDS = [
    "attractions", "scenic", "spots", "places to visit", "recommend places",
    "景点", "景区", "推荐地方", "去哪玩", "适合去的地方",
]

# =========================================================
# City aliases
# =========================================================

CITY_ALIASES = {
    "beijing": "Beijing", "北京": "Beijing", "北京市": "Beijing",
    "shanghai": "Shanghai", "上海": "Shanghai", "上海市": "Shanghai",
    "guangzhou": "Guangzhou", "广州": "Guangzhou",
    "shenzhen": "Shenzhen", "深圳": "Shenzhen",
    "hong kong": "Hong Kong", "香港": "Hong Kong",
    "hangzhou": "Hangzhou", "杭州": "Hangzhou",
    "nanjing": "Nanjing", "南京": "Nanjing",
    "suzhou": "Suzhou", "苏州": "Suzhou",
    "chengdu": "Chengdu", "成都": "Chengdu",
    "wuhan": "Wuhan", "武汉": "Wuhan",
    "xian": "Xi'an", "xi'an": "Xi'an", "西安": "Xi'an",
}

PET_TYPES = {
    "dog": ["dog", "puppy", "狗", "狗狗", "小狗", "犬"],
    "cat": ["cat", "kitten", "猫", "猫咪", "小猫"],
}

# =========================================================
# Chinese numeral helpers
# =========================================================

CHINESE_NUMERAL_MAP = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8,
    "九": 9, "十": 10,
}

CHINESE_MONTH_MAP = {
    "一月": 1, "二月": 2, "三月": 3, "四月": 4,
    "五月": 5, "六月": 6, "七月": 7, "八月": 8,
    "九月": 9, "十月": 10, "十一月": 11, "十二月": 12,
}

def _normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _convert_simple_chinese_numeral(token: str) -> Optional[int]:
    token = (token or "").strip()
    if not token:
        return None

    if token.isdigit():
        return int(token)

    if token in CHINESE_NUMERAL_MAP:
        return CHINESE_NUMERAL_MAP[token]

    if token == "十":
        return 10

    if len(token) == 2 and token[0] == "十":
        return 10 + CHINESE_NUMERAL_MAP.get(token[1], 0)

    if len(token) == 2 and token[1] == "十":
        return CHINESE_NUMERAL_MAP.get(token[0], 0) * 10

    if len(token) == 3 and token[1] == "十":
        return CHINESE_NUMERAL_MAP.get(token[0], 0) * 10 + CHINESE_NUMERAL_MAP.get(token[2], 0)

    return None


def _convert_chinese_month(token: str) -> Optional[int]:
    token = token.strip()
    if token.isdigit():
        return int(token)
    if token in CHINESE_MONTH_MAP:
        return CHINESE_MONTH_MAP[token]
    return _convert_simple_chinese_numeral(token.replace("月", ""))

# =========================================================
# Stage & feature detection
# =========================================================

def _detect_stage(text: str) -> StageEnum:
    t = _normalize_text(text)
    intrip_keywords = [
        "right now", "currently", "near me", "traffic", "emergency",
        "现在", "目前", "附近", "堵车", "突发", "紧急",
    ]
    return StageEnum.IN_TRIP if _contains_any(t, intrip_keywords) else StageEnum.PRE_TRIP


def _detect_feature_id(text: str, stage: StageEnum) -> FeatureIdEnum:
    t = _normalize_text(text)

    if stage == StageEnum.PRE_TRIP:
        if _contains_any(t, DOCUMENT_KEYWORDS):
            return FeatureIdEnum.DOCUMENT_MATERIAL_REMINDER
        if _contains_any(t, SCENIC_KEYWORDS):
            return FeatureIdEnum.SCENIC_RECOMMENDATION
        return FeatureIdEnum.TRAVEL_ROUTE_PLANNING

    if stage == StageEnum.IN_TRIP:
        if _contains_any(t, ["pet hospital", "兽医", "宠物医院"]):
            return FeatureIdEnum.NEARBY_PET_HOSPITAL_RECOMMENDATION
        if _contains_any(t, ["hospital", "医院", "急诊"]):
            return FeatureIdEnum.NEARBY_HOSPITAL_RECOMMENDATION
        return FeatureIdEnum.ROUTE_REPLANNING

    return FeatureIdEnum.TRAVEL_ROUTE_PLANNING

# =========================================================
# Field extraction
# =========================================================

def _extract_city(text: str) -> Optional[str]:
    t = _normalize_text(text)
    for alias, normalized in CITY_ALIASES.items():
        if alias in t:
            return normalized
    return None

def _extract_date(text: str) -> Optional[str]:
    # ---- Western formats: YYYY-MM-DD / YYYY/MM/DD ----
    m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if m:
        y, mth, d = m.groups()
        return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"

    # ---- Western formats: DD-MM-YYYY / DD/MM/YYYY ----
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](20\d{2})", text)
    if m:
        d, mth, y = m.groups()
        return f"{int(y):04d}-{int(mth):02d}-{int(d):02d}"

    # ---- Chinese full date: 2026年5月10日 ----
    m = re.search(
        r"(20\d{2})\s*年\s*([\d一二三四五六七八九十]+)\s*月\s*([\d一二三四五六七八九十]+)\s*[日号]?",
        text,
    )
    if m:
        year = int(m.group(1))
        month = _convert_chinese_month(m.group(2))
        day = _convert_simple_chinese_numeral(m.group(3))
        if month and day:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # ---- Chinese month/day only: 5月10日 ----
    m = re.search(
        r"([\d一二三四五六七八九十]+)\s*月\s*([\d一二三四五六七八九十]+)\s*[日号]?",
        text,
    )
    if m:
        month = _convert_chinese_month(m.group(1))
        day = _convert_simple_chinese_numeral(m.group(2))
        if month and day:
            year = datetime.now().year
            return f"{year:04d}-{month:02d}-{day:02d}"

    return None

def _extract_trip_days(text: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*(?:days?|天)", text)
    if m:
        return int(m.group(1))

    m = re.search(r"([一二两三四五六七八九十]+)\s*天", text)
    if m:
        return _convert_simple_chinese_numeral(m.group(1))

    return None


def _extract_daily_play_hours(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|小时)", text)
    return float(m.group(1)) if m else None


def _extract_pet_type(text: str) -> Optional[str]:
    t = _normalize_text(text)
    for pet, variants in PET_TYPES.items():
        if any(v in t for v in variants):
            return pet
    return None


def _extract_pet_age(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|岁)", text)
    if m:
        return float(m.group(1))
    m = re.search(r"([一二两三四五六七八九十]+)\s*岁", text)
    if m:
        value = _convert_simple_chinese_numeral(m.group(1))
        return float(value) if value is not None else None
    return None


def _extract_pet_weight(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)", text)
    return float(m.group(1)) if m else None


def _extract_transport_preference(text: str) -> Optional[str]:
    t = _normalize_text(text)

    ordered_patterns = {
        "high_speed_rail": [r"\bhigh speed rail\b", r"\bhigh-speed rail\b", r"\bhsr\b", r"\bbullet train\b", "高铁"],
        "public_transport": [r"\bpublic transport\b", r"\bmetro\b", r"\bsubway\b", r"\bbus\b", r"\bmtr\b", "地铁", "公交", "公共交通"],
        "private_car": [r"\bself-driving\b", r"\bself driving\b", r"\bdriving\b", r"\bdrive\b", r"\bcar\b", "自驾", "开车", "私家车"],
        "shared_bike": [r"\bshared bike\b", r"\bbike\b", r"\bcycling\b", "骑车", "共享单车"],
        "taxi": [r"\btaxi\b", r"\bcab\b", "打车", "出租车"],
        "walk": [r"\bwalking\b", r"\bwalk\b", "步行"],
        "rail": [r"\btrain\b", r"\brail\b", "火车", "铁路"],
        "flight": [r"\bflight\b", r"\bplane\b", r"\bairplane\b", "飞机", "航班"],
    }

    for normalized, patterns in ordered_patterns.items():
        for p in patterns:
            if p.startswith(r"\b"):
                if re.search(p, t):
                    return normalized
            elif p in t:
                return normalized
    return None


def _extract_budget_total(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|rmb|yuan|cny)", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _extract_fields(text: str) -> Dict[str, Any]:
    return {
        "destination_city": _extract_city(text),
        "travel_start_date": _extract_date(text),
        "trip_days": _extract_trip_days(text),
        "daily_play_hours": _extract_daily_play_hours(text),
        "transport_preference": _extract_transport_preference(text),
        "budget_total": _extract_budget_total(text),
        "pet_type": _extract_pet_type(text),
        "pet_age": _extract_pet_age(text),
        "pet_weight_kg": _extract_pet_weight(text),
    }

# =========================================================
# Memory merge & routing
# =========================================================

def _merge_with_memory(
    extracted_fields: Dict[str, Any],
    memory_summary: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not memory_summary:
        return extracted_fields

    merged = dict(extracted_fields)
    for key, value in memory_summary.items():
        if merged.get(key) in (None, "", []):
            merged[key] = value
    return merged


def _build_structured_task_stub_json(
    stage: StageEnum,
    feature_id: FeatureIdEnum,
    recognized_field_values: Dict[str, Any],
) -> StructuredTaskStubJson:
    return StructuredTaskStubJson(
        recognized_stage=stage,
        recognized_task=feature_id,
        recognized_field_values=recognized_field_values,
    )


def _build_tool_invocation_decision(
    feature_id: FeatureIdEnum,
    planner_allowed: bool,
) -> ToolInvocationDecision:
    if planner_allowed:
        return ToolInvocationDecision.READY_FOR_PLANNER

    planner_features = {
        FeatureIdEnum.TRAVEL_ROUTE_PLANNING,
        FeatureIdEnum.ROUTE_REPLANNING,
        FeatureIdEnum.NEARBY_HOSPITAL_RECOMMENDATION,
        FeatureIdEnum.NEARBY_PET_HOSPITAL_RECOMMENDATION,
        FeatureIdEnum.ALTERNATIVE_SCENIC_RECOMMENDATION,
    }

    return (
        ToolInvocationDecision.BLOCKED_BY_MISSING_FIELDS
        if feature_id in planner_features
        else ToolInvocationDecision.NO_TOOL_NEEDED
    )


def route_user_message(
    current_user_message: str,
    memory_summary: Optional[Dict[str, Any]] = None,
) -> RouterOutput:
    stage = _detect_stage(current_user_message)
    feature_id = _detect_feature_id(current_user_message, stage)

    extracted_fields = _extract_fields(current_user_message)
    recognized_field_values = _merge_with_memory(extracted_fields, memory_summary)

    validation_result = validate_feature_fields(
        feature_id=feature_id,
        extracted_fields=recognized_field_values,
    )

    planner_allowed = should_invoke_planner(
        feature_id=feature_id,
        validation_result=validation_result,
    )

    tool_decision = _build_tool_invocation_decision(
        feature_id=feature_id,
        planner_allowed=planner_allowed,
    )

    structured_task_stub_json = _build_structured_task_stub_json(
        stage=stage,
        feature_id=feature_id,
        recognized_field_values=recognized_field_values,
    )

    return RouterOutput(
        recognized_stage=stage,
        recognized_task=feature_id,
        recognized_field_values=recognized_field_values,
        missing_fields_resolution_status=validation_result,
        tool_invocation_decision=tool_decision,
        structured_task_stub_json=structured_task_stub_json,
    )


def route_message(
    current_user_message: str,
    memory_summary: Optional[Dict[str, Any]] = None,
) -> RouterOutput:
    return route_user_message(
        current_user_message=current_user_message,
        memory_summary=memory_summary,
    )