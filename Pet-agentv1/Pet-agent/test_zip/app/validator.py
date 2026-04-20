from __future__ import annotations

from typing import Any, Dict, List, Optional

from schemas import (
    FeatureIdEnum,
    MissingFieldsResolutionStatus,
    RouterOutput,
)


REQUIRED_FIELDS_BY_FEATURE: Dict[FeatureIdEnum, List[str]] = {
    FeatureIdEnum.TRAVEL_ROUTE_PLANNING: [
        "destination_city",
        "travel_start_date",
        "trip_days",
        "daily_play_hours",
        "transport_preference",
        "pet_type",
        "pet_age",
        "pet_weight_kg",
    ],
    FeatureIdEnum.DOCUMENT_MATERIAL_REMINDER: [
        "destination_city",
        "pet_type",
    ],
    FeatureIdEnum.SCENIC_RECOMMENDATION: [
        "destination_city",
        "pet_type",
        "pet_age",
        "pet_weight_kg",
    ],
    FeatureIdEnum.ROUTE_REPLANNING: [
        "destination_city",
    ],
    FeatureIdEnum.NEARBY_HOSPITAL_RECOMMENDATION: [
        "destination_city",
    ],
    FeatureIdEnum.NEARBY_PET_HOSPITAL_RECOMMENDATION: [
        "destination_city",
        "pet_type",
    ],
    FeatureIdEnum.ALTERNATIVE_SCENIC_RECOMMENDATION: [
        "destination_city",
        "pet_type",
    ],
}


PLANNER_ROUTED_FEATURES = {
    FeatureIdEnum.TRAVEL_ROUTE_PLANNING,
    FeatureIdEnum.ROUTE_REPLANNING,
    FeatureIdEnum.NEARBY_HOSPITAL_RECOMMENDATION,
    FeatureIdEnum.NEARBY_PET_HOSPITAL_RECOMMENDATION,
    FeatureIdEnum.ALTERNATIVE_SCENIC_RECOMMENDATION,
}


FOLLOW_UP_QUESTION_MAP: Dict[str, str] = {
    "destination_city": "Which city are you traveling to?",
    "travel_start_date": "What is your travel start date?",
    "travel_end_date": "What is your travel end date?",
    "trip_days": "How many travel days are you planning for this trip?",
    "daily_play_hours": "How many hours per day do you want to spend sightseeing?",
    "transport_preference": "What is your preferred transportation mode for this trip?",
    "pet_type": "What type of pet are you traveling with?",
    "pet_age": "How old is your pet?",
    "pet_weight_kg": "What is your pet's weight in kilograms?",
    "budget_total": "What is your total budget for the trip?",
    "budget_per_person": "What is your budget per person?",
}


VALID_TRANSPORT_PREFERENCES = {
    "walk",
    "taxi",
    "car",
    "shared_bike",
    "public_transport",
}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def _safe_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_missing_fields(
    required_fields: List[str],
    extracted_fields: Dict[str, Any],
) -> List[str]:
    missing: List[str] = []
    for field in required_fields:
        if _is_missing(extracted_fields.get(field)):
            missing.append(field)
    return missing


def _build_follow_up_question(
    missing_fields: List[str],
    blocking_fields: List[str],
) -> Optional[str]:
    if missing_fields:
        first_missing = missing_fields[0]
        return FOLLOW_UP_QUESTION_MAP.get(
            first_missing,
            f"Please provide {first_missing}.",
        )

    if blocking_fields:
        first_blocking = blocking_fields[0]
        return f"The value for {first_blocking} looks invalid. Please provide a valid {first_blocking}."

    return None


def _check_common_numeric_rules(extracted_fields: Dict[str, Any]) -> List[str]:
    blocking_fields: List[str] = []

    trip_days_num = _safe_number(extracted_fields.get("trip_days"))
    if extracted_fields.get("trip_days") is not None and (trip_days_num is None or trip_days_num <= 0):
        blocking_fields.append("trip_days")

    daily_play_hours_num = _safe_number(extracted_fields.get("daily_play_hours"))
    if extracted_fields.get("daily_play_hours") is not None and (
        daily_play_hours_num is None or daily_play_hours_num <= 0 or daily_play_hours_num > 24
    ):
        blocking_fields.append("daily_play_hours")

    pet_age_num = _safe_number(extracted_fields.get("pet_age"))
    if extracted_fields.get("pet_age") is not None and (pet_age_num is None or pet_age_num < 0):
        blocking_fields.append("pet_age")

    pet_weight_num = _safe_number(extracted_fields.get("pet_weight_kg"))
    if extracted_fields.get("pet_weight_kg") is not None and (pet_weight_num is None or pet_weight_num <= 0):
        blocking_fields.append("pet_weight_kg")

    budget_total_num = _safe_number(extracted_fields.get("budget_total"))
    if extracted_fields.get("budget_total") is not None and (budget_total_num is None or budget_total_num < 0):
        blocking_fields.append("budget_total")

    budget_per_person_num = _safe_number(extracted_fields.get("budget_per_person"))
    if extracted_fields.get("budget_per_person") is not None and (
        budget_per_person_num is None or budget_per_person_num < 0
    ):
        blocking_fields.append("budget_per_person")

    return blocking_fields


def _check_feature_specific_rules(
    feature_id: FeatureIdEnum,
    extracted_fields: Dict[str, Any],
) -> List[str]:
    blocking_fields: List[str] = []

    pet_weight_num = _safe_number(extracted_fields.get("pet_weight_kg"))
    transport_preference = extracted_fields.get("transport_preference")

    if feature_id == FeatureIdEnum.TRAVEL_ROUTE_PLANNING:
        if pet_weight_num is not None and pet_weight_num > 50:
            blocking_fields.append("pet_weight_kg")

        if transport_preference and transport_preference not in VALID_TRANSPORT_PREFERENCES:
            blocking_fields.append("transport_preference")

    return blocking_fields


def _check_business_rules(
    feature_id: FeatureIdEnum,
    extracted_fields: Dict[str, Any],
) -> List[str]:
    blocking_fields = []
    blocking_fields.extend(_check_common_numeric_rules(extracted_fields))
    blocking_fields.extend(_check_feature_specific_rules(feature_id, extracted_fields))

    seen = set()
    deduplicated = []
    for field in blocking_fields:
        if field not in seen:
            seen.add(field)
            deduplicated.append(field)
    return deduplicated


def validate_feature_fields(
    feature_id: FeatureIdEnum,
    extracted_fields: Dict[str, Any],
) -> MissingFieldsResolutionStatus:
    required_fields = REQUIRED_FIELDS_BY_FEATURE.get(feature_id, [])
    missing_required_fields = _collect_missing_fields(required_fields, extracted_fields)
    blocking_fields = _check_business_rules(feature_id, extracted_fields)

    is_complete = len(missing_required_fields) == 0 and len(blocking_fields) == 0
    follow_up_question = _build_follow_up_question(
        missing_fields=missing_required_fields,
        blocking_fields=blocking_fields,
    )

    return MissingFieldsResolutionStatus(
        is_complete=is_complete,
        missing_required_fields=missing_required_fields,
        blocking_fields=blocking_fields,
        follow_up_question=follow_up_question,
    )


def should_invoke_planner(
    feature_id: FeatureIdEnum,
    validation_result: MissingFieldsResolutionStatus,
) -> bool:
    return feature_id in PLANNER_ROUTED_FEATURES and validation_result.is_complete


def validate_travel_route_planning(
    extracted_fields: Dict[str, Any],
) -> MissingFieldsResolutionStatus:
    return validate_feature_fields(
        FeatureIdEnum.TRAVEL_ROUTE_PLANNING,
        extracted_fields,
    )


def validate_document_material_reminder(
    extracted_fields: Dict[str, Any],
) -> MissingFieldsResolutionStatus:
    return validate_feature_fields(
        FeatureIdEnum.DOCUMENT_MATERIAL_REMINDER,
        extracted_fields,
    )


def validate_router_output(
    router_output: RouterOutput,
) -> MissingFieldsResolutionStatus:
    return validate_feature_fields(
        feature_id=router_output.recognized_task,
        extracted_fields=router_output.recognized_field_values,
    )