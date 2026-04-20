from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from uuid import uuid4

from .cosmos_client import CosmosDataClient
from .rule_classifier import classify_json_record

_CLIENT = CosmosDataClient.from_env()


def _row_text(row: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(row.get("domain", "")),
            str(row.get("subtype", "")),
            str(row.get("source_type", "")),
            str(row.get("source_file", "")),
            str(row.get("title", "")),
            str(row.get("condition", "")),
            str(row.get("summary", "")),
            str(row.get("constraint_description", "")),
            str(row.get("action_required", "")),
        ]
    ).lower()


def _row_source_type(row: Dict[str, Any]) -> str:
    return str(row.get("source_type", "")).strip().lower()


def _row_domain(row: Dict[str, Any]) -> str:
    return str(row.get("domain", "")).strip().lower()


def _row_subtype(row: Dict[str, Any]) -> str:
    return str(row.get("subtype", "")).strip().lower()


def _infer_rule_family(row: Dict[str, Any]) -> str:
    return classify_json_record(row)["record_type"]


def _transport_mode_hints_from_row(row: Dict[str, Any]) -> List[str]:
    subtype = _row_subtype(row)
    source_file = str(row.get("source_file", "")).lower()
    text = _row_text(row)

    hints: List[str] = []

    def _add(value: str) -> None:
        if value not in hints:
            hints.append(value)

    if "rail" in subtype or "rail" in source_file or "rail" in text:
        _add("train")
    if any(token in subtype for token in ["air", "flight"]) or "air" in source_file or any(token in text for token in ["air", "flight"]):
        _add("flight")
    if any(token in subtype for token in ["urban_transit", "urban transit", "transit"]) or "urban" in source_file or "urban transit" in text:
        _add("urban_transit")
    if any(token in subtype for token in ["drive", "driving", "car", "road"]) or any(k in text for k in ["driving", "car", "road"]):
        _add("car")
    if any(token in subtype for token in ["walk", "walking"]) or any(k in text for k in ["walk", "walking"]):
        _add("walking")
    if "bus" in subtype or "bus" in text:
        _add("bus")

    return hints


def _bucket_social_row(row: Dict[str, Any]) -> str:
    source_type = _row_source_type(row)
    if source_type == "content_sop":
        return "sop"
    if source_type == "comment_edgecase":
        return "edge_cases"
    return "unknown"


def _build_social_context_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    title = str(row.get("title") or row.get("condition") or "")
    condition = str(row.get("condition") or "")
    constraint = str(row.get("constraint_description") or row.get("summary") or "")
    action_required = str(row.get("action_required") or "")
    source_platform = str(row.get("source_platform") or "")
    source_type = str(row.get("source_type") or "")

    if source_type == "Comment_EdgeCase":
        context = " | ".join(part for part in [title, condition, constraint] if part)
    else:
        context = " | ".join(part for part in [title, constraint, action_required] if part)

    return {
        "id": row.get("id"),
        "domain": row.get("domain"),
        "source_type": row.get("source_type"),
        "source_platform": source_platform,
        "condition": condition,
        "constraint_description": constraint,
        "action_required": action_required,
        "context_text": context,
    }


def _fetch_rule_rows(limit: int) -> List[Dict[str, Any]]:
    query = (
        "SELECT TOP @limit c.id, c.type, c.domain, c.subtype, c.source_type, c.source_file, "
        "c.title, c.condition, c.summary, c.constraint_description, c.action_required, c.source_platform "
        "FROM c WHERE c.type = 'rule'"
    )
    params = [{"name": "@limit", "value": limit}]
    return _CLIENT.query_items(query=query, parameters=params)


def get_data_layer_health() -> Dict[str, Any]:
    return {
        "cosmos_connected": _CLIENT.ping(),
        "database": "JingHuPetProject",
        "container": "MainData",
    }


def get_rule_documents(limit: int = 5) -> Tuple[List[Dict[str, Any]], str]:
    query = "SELECT TOP @limit c.id, c.type, c.subtype, c.source_file FROM c WHERE c.type = 'rule'"
    params = [{"name": "@limit", "value": limit}]
    try:
        docs = _CLIENT.query_items(query=query, parameters=params)
        return docs, "cosmos"
    except Exception:
        return [], "cosmos_unavailable"


def get_pet_profiles(species: str, limit: int = 3) -> Tuple[List[Dict[str, Any]], str]:
    type_name = "cat_profile" if species == "cat" else "dog_profile"
    query = "SELECT TOP @limit c.id, c.breed_name, c.weight, c.life_expectancy, c.lifespan FROM c WHERE c.type = @type"
    params = [{"name": "@limit", "value": limit}, {"name": "@type", "value": type_name}]
    try:
        docs = _CLIENT.query_items(query=query, parameters=params)
        return docs, "cosmos"
    except Exception:
        return [], "cosmos_unavailable"


def get_agent_policy_excerpt(max_chars: int = 500) -> Tuple[str, str]:
    query = "SELECT TOP 1 c.content_md FROM c WHERE c.type = 'agent_policy'"
    try:
        items = _CLIENT.query_items(query=query)
        if not items:
            return "", "cosmos"
        return str(items[0].get("content_md", ""))[:max_chars], "cosmos"
    except Exception:
        return "", "cosmos_unavailable"


def get_transport_context(departure: str, destination: str) -> Tuple[Dict[str, Any], str]:
    try:
        docs = _fetch_rule_rows(limit=60)
        mode_hints = set()
        transport_rule_refs: List[Any] = []
        transport_social_sop_refs: List[Any] = []
        transport_social_edge_refs: List[Any] = []
        social_context = {"sop": [], "edge_cases": []}

        for row in docs:
            classification = classify_json_record(row)
            source_type = _row_source_type(row)
            is_transport = classification.get("agent") == "traffic"

            if not is_transport:
                continue

            transport_rule_refs.append(row.get("id"))

            if source_type in {"content_sop", "comment_edgecase"}:
                bucket = _bucket_social_row(row)
                entry = _build_social_context_entry(row)
                social_context[bucket].append(entry)
                if bucket == "sop":
                    transport_social_sop_refs.append(row.get("id"))
                elif bucket == "edge_cases":
                    transport_social_edge_refs.append(row.get("id"))

            for hint in _transport_mode_hints_from_row(row):
                mode_hints.add(hint)

        return {
            "route": f"{departure} -> {destination}",
            "supported_modes": sorted(mode_hints),
            "rule_refs": transport_rule_refs[:8],
            "transport_rule_refs": transport_rule_refs,
            "social_context": {
                "sop": social_context["sop"][:10],
                "edge_cases": social_context["edge_cases"][:10],
                "sop_refs": transport_social_sop_refs[:10],
                "edge_case_refs": transport_social_edge_refs[:10],
            },
            "notes": [
                "Transport context inferred from Cosmos rule documents.",
                "Content_SOP rows are treated as standard operational guidance.",
                "Comment_EdgeCase rows are treated as anecdotal edge-case guidance.",
            ],
        }, "cosmos"
    except Exception:
        return {
            "route": f"{departure} -> {destination}",
            "supported_modes": [],
            "rule_refs": [],
            "transport_rule_refs": [],
            "social_context": {
                "sop": [],
                "edge_cases": [],
                "sop_refs": [],
                "edge_case_refs": [],
            },
            "notes": ["Transport context unavailable from Cosmos at runtime."],
        }, "cosmos_unavailable"


def get_lodging_context(destination: str, pet_type: str) -> Tuple[Dict[str, Any], str]:
    query = "SELECT TOP 20 c.id, c.city, c.hotel_name, c.name, c.pet_policy FROM c WHERE c.type = 'lodging'"
    params = []
    try:
        rows = _CLIENT.query_items(query=query, parameters=params)
        normalized = []
        for row in rows:
            city = str(row.get("city") or "")
            if city and city.lower() != destination.lower():
                continue
            normalized.append(
                {
                    "id": row.get("id"),
                    "name": row.get("hotel_name") or row.get("name"),
                    "pet_policy": row.get("pet_policy", ""),
                }
            )

        return {
            "city": destination,
            "pet_type": pet_type,
            "recommended_hotels": [h.get("name") for h in normalized if h.get("name")][:5],
            "hotel_records": normalized[:5],
            "notes": ["Operational context loaded from Cosmos lodging documents."] if normalized else ["No lodging rows found in Cosmos for this city."],
        }, "cosmos"
    except Exception:
        return {
            "city": destination,
            "pet_type": pet_type,
            "recommended_hotels": [],
            "hotel_records": [],
            "notes": ["Lodging context unavailable from Cosmos at runtime."],
        }, "cosmos_unavailable"


def get_experience_context(destination: str, pet_type: str, limit: int = 60) -> Tuple[Dict[str, Any], str]:
    try:
        rows = _fetch_rule_rows(limit=limit)
        domain_buckets = {
            "accommodation": [],
            "attractions": [],
            "health": [],
            "food_services": [],
        }
        social_context = {
            "sop": [],
            "edge_cases": [],
        }
        social_refs = {
            "sop": [],
            "edge_cases": [],
        }

        for row in rows:
            classification = classify_json_record(row)
            source_type = _row_source_type(row)

            is_experience = classification.get("agent") == "experience"

            if not is_experience:
                continue

            text = _row_text(row)

            if any(k in text for k in ["hotel", "accommodation", "lodging"]):
                domain_buckets["accommodation"].append(row.get("id"))
            if any(k in text for k in ["attraction", "scenic", "poi", "park", "museum"]):
                domain_buckets["attractions"].append(row.get("id"))
            if any(k in text for k in ["health", "hospital", "vet", "stress", "heat", "medical"]):
                domain_buckets["health"].append(row.get("id"))
            if any(k in text for k in ["food", "restaurant", "dining", "snack"]):
                domain_buckets["food_services"].append(row.get("id"))

            if source_type in {"content_sop", "comment_edgecase"}:
                bucket = _bucket_social_row(row)
                entry = _build_social_context_entry(row)
                social_context[bucket].append(entry)
                social_refs[bucket].append(row.get("id"))

        pet_profiles, profile_source = get_pet_profiles(species=(pet_type or "dog"), limit=3)
        return {
            "city": destination,
            "pet_type": pet_type,
            "domain_rule_refs": {k: v[:8] for k, v in domain_buckets.items()},
            "social_context": {
                "sop": social_context["sop"][:10],
                "edge_cases": social_context["edge_cases"][:10],
                "sop_refs": social_refs["sop"][:10],
                "edge_case_refs": social_refs["edge_cases"][:10],
            },
            "pet_profile_refs": [row.get("id") for row in pet_profiles],
            "pet_profiles": pet_profiles,
            "notes": [
                "Experience context inferred from mixed rule documents + pet profiles.",
                "Content_SOP rows are treated as standard recommendation guidance.",
                "Comment_EdgeCase rows are treated as anecdotal edge-case guidance.",
                f"Pet profiles source: {profile_source}",
            ],
        }, "cosmos"
    except Exception:
        return {
            "city": destination,
            "pet_type": pet_type,
            "domain_rule_refs": {
                "accommodation": [],
                "attractions": [],
                "health": [],
                "food_services": [],
            },
            "social_context": {
                "sop": [],
                "edge_cases": [],
                "sop_refs": [],
                "edge_case_refs": [],
            },
            "pet_profile_refs": [],
            "pet_profiles": [],
            "recommended_hotels": [],
            "notes": ["Experience context unavailable from Cosmos at runtime."],
        }, "cosmos_unavailable"


def append_session_memory(entry: Dict[str, Any]) -> Tuple[bool, str]:
    payload = dict(entry)
    payload.setdefault("id", f"session_memory_{uuid4().hex}")
    payload["type"] = "session_memory"
    payload.setdefault("subtype", "member7_run")
    payload.setdefault("ingested_at", datetime.now(timezone.utc).isoformat())

    try:
        _CLIENT.upsert_item(payload)
        return True, "cosmos"
    except Exception:
        return False, "file_fallback"


def load_session_memory(limit: int = 20) -> Tuple[List[Dict[str, Any]], str]:
    query = "SELECT TOP @limit * FROM c WHERE c.type = 'session_memory'"
    params = [{"name": "@limit", "value": limit}]
    try:
        rows = _CLIENT.query_items(query=query, parameters=params)
        return rows, "cosmos"
    except Exception:
        return [], "file_fallback"

