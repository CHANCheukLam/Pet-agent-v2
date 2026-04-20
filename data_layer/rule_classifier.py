from __future__ import annotations

from typing import Any, Dict, Iterable, List

TRANSPORT_DOMAINS = {"transport", "traffic"}
EXPERIENCE_DOMAINS = {"accommodation", "lodging", "attractions", "attraction", "health", "food", "food services", "food_services"}
POLICY_TYPES = {"agent_policy", "policy", "hard_policy"}

TRANSPORT_SUBTYPE_PREFIXES = (
    "transport_rule_",
    "traffic_rule_",
    "metro_rule_",
    "bus_rule_",
    "tram_rule_",
    "rail_rule_",
    "air_rule_",
)

EXPERIENCE_SUBTYPE_PREFIXES = (
    "accommodation_rule_",
    "lodging_rule_",
    "attraction_rule_",
    "health_rule_",
    "food_rule_",
    "food_service_rule_",
)

POLICY_HINTS = (
    "decision_policy",
    "hard_stop",
    "hard stop",
    "final decision",
    "allow only if explicit exception",
    "allow_only_if_explicit_exception",
    "agent_decision_notes",
    "policy_summary",
    "默认规则",
    "禁止",
    "明确例外",
    "最终裁决",
    "不允许",
    "硬性",
)

TRANSPORT_HINTS = (
    "transport",
    "transportation",
    "traffic",
    "route",
    "rail",
    "metro",
    "subway",
    "light rail",
    "tram",
    "bus",
    "air",
    "flight",
    "car",
    "driving",
    "walking",
    "交通",
    "出行",
    "轨道交通",
    "地铁",
    "轻轨",
    "公交",
    "高铁",
    "火车",
    "航班",
    "飞机",
    "自驾",
)

EXPERIENCE_HINTS = (
    "hotel",
    "accommodation",
    "lodging",
    "attraction",
    "scenic",
    "poi",
    "park",
    "museum",
    "health",
    "hospital",
    "vet",
    "food",
    "restaurant",
    "dining",
    "snack",
    "住宿",
    "酒店",
    "民宿",
    "景点",
    "医院",
    "宠物医院",
    "餐厅",
    "美食",
    "吃饭",
    "健康",
)


def _stringify(value: Any) -> Iterable[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        parts: List[str] = []
        for key, sub_value in value.items():
            parts.extend(_stringify(key))
            parts.extend(_stringify(sub_value))
        return parts
    if isinstance(value, (list, tuple, set)):
        parts: List[str] = []
        for item in value:
            parts.extend(_stringify(item))
        return parts
    return [str(value)]


def _text_blob(record: Dict[str, Any]) -> str:
    return " ".join(part for part in _stringify(record)).lower()


def _normalized(record: Dict[str, Any], key: str) -> str:
    return str(record.get(key, "")).strip().lower()


def _has_prefix(value: str, prefixes: Iterable[str]) -> bool:
    return any(value.startswith(prefix) for prefix in prefixes)


def classify_json_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Classify a JSON record into an agent bucket.

    Returns a normalized routing payload with:
    - agent: traffic / experience / compliance / unknown
    - record_type: policy / transport / experience / unknown
    - needs_clarification: whether the record is too ambiguous to route safely
    - matched_clues: useful signals that triggered the decision
    - reason: human-readable explanation
    """

    blob = _text_blob(record)
    record_type = _normalized(record, "type")
    domain = _normalized(record, "domain")
    subtype = _normalized(record, "subtype")
    source_type = _normalized(record, "source_type")

    matched_clues: List[str] = []

    def add_clue(clue: str) -> None:
        if clue not in matched_clues:
            matched_clues.append(clue)

    # Hard policy / compliance always wins.
    policy_markers = {
        key for key in ("decision_policy", "agent_decision_notes", "policy_summary", "hard_stop_semantics") if key in record
    }
    if record_type in POLICY_TYPES or policy_markers or any(hint in blob for hint in POLICY_HINTS):
        if record_type in POLICY_TYPES:
            add_clue(f"type={record_type}")
        for marker in sorted(policy_markers):
            add_clue(f"field={marker}")
        if any(hint in blob for hint in POLICY_HINTS):
            add_clue("policy_hints")
        return {
            "agent": "compliance",
            "record_type": "policy",
            "needs_clarification": False,
            "matched_clues": matched_clues,
            "reason": "Policy or hard-rule record; route to compliance.",
        }

    # Transport first for route / mobility rules.
    if domain in TRANSPORT_DOMAINS:
        add_clue(f"domain={domain}")
        return {
            "agent": "traffic",
            "record_type": "transport",
            "needs_clarification": False,
            "matched_clues": matched_clues,
            "reason": "Transport domain record; route to traffic.",
        }

    if subtype and _has_prefix(subtype, TRANSPORT_SUBTYPE_PREFIXES):
        add_clue(f"subtype={subtype}")
        return {
            "agent": "traffic",
            "record_type": "transport",
            "needs_clarification": False,
            "matched_clues": matched_clues,
            "reason": "Transport subtype record; route to traffic.",
        }

    if any(hint in blob for hint in TRANSPORT_HINTS):
        add_clue("transport_hints")
        return {
            "agent": "traffic",
            "record_type": "transport",
            "needs_clarification": False,
            "matched_clues": matched_clues,
            "reason": "Transport keywords found in content; route to traffic.",
        }

    # Experience covers accommodation, attraction, food, and health guidance.
    if domain in EXPERIENCE_DOMAINS:
        add_clue(f"domain={domain}")
        return {
            "agent": "experience",
            "record_type": "experience",
            "needs_clarification": False,
            "matched_clues": matched_clues,
            "reason": "Experience-related domain record; route to experience.",
        }

    if subtype and _has_prefix(subtype, EXPERIENCE_SUBTYPE_PREFIXES):
        add_clue(f"subtype={subtype}")
        return {
            "agent": "experience",
            "record_type": "experience",
            "needs_clarification": False,
            "matched_clues": matched_clues,
            "reason": "Experience-related subtype record; route to experience.",
        }

    if any(hint in blob for hint in EXPERIENCE_HINTS):
        add_clue("experience_hints")
        return {
            "agent": "experience",
            "record_type": "experience",
            "needs_clarification": False,
            "matched_clues": matched_clues,
            "reason": "Experience keywords found in content; route to experience.",
        }

    # Source type alone is not enough to route, but we keep it for traceability.
    if source_type:
        add_clue(f"source_type={source_type}")

    return {
        "agent": "unknown",
        "record_type": "unknown",
        "needs_clarification": True,
        "matched_clues": matched_clues,
        "reason": "Missing or ambiguous routing clues; keep unknown and clarify.",
    }


def route_json_record(record: Dict[str, Any]) -> str:
    return classify_json_record(record)["agent"]


