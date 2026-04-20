from __future__ import annotations

from typing import Any, Dict, Optional

from schemas import (
    CandidateResourceSummary,
    ConstraintSummary,
    FeatureIdEnum,
    HardRules,
    LiveContext,
    NormalizedRequestJson,
    OutputLanguage,
    PetProfile,
    PlannerHandoffPayload,
    RequiredOutputFormat,
    RouterOutput,
    SoftEvidence,
    ToolInvocationDecision,
    UserProfile,
)


STATIC_PET_PROFILE_SOURCES = (
    "data/static/pet_profiles/Cat_PURINA_data_cleaned_for_cosmos.json | "
    "data/static/pet_profiles/Dog_AKC_data_cleaned_for_cosmos.json | "
    "data/static/pet_profiles/Cat_TICA_data_cleaned_no_weight_data.json"
)

STATIC_TRANSPORT_RULE_SOURCES = (
    "data/static/transport_rules/pet_air_transport_rules_cn_jinghu_compact_rules_engine_v1.json | "
    "data/static/transport_rules/pet_rail_transport_rules_cn_hsr_v1.json | "
    "data/static/transport_rules/pet_urban_transit_rules_beijing_shanghai_rules_engine_v1.json | "
    "AGENTS.md"
)

MOCK_WEATHER_SOURCE = "data/mock/weather/tool.qweather.forecast.json"
MOCK_ROUTE_SOURCE = "data/mock/maps/tool.gaode.route_matrix.json"
MOCK_POI_SOURCE = (
    "data/mock/maps/tool.gaode.poi_keyword.json | "
    "data/mock/maps/tool.gaode.poi_detail.json"
)
MOCK_HOTEL_SOURCE = "data/mock/hotels/hotel_candidates_mock.json"
MOCK_PET_HOSPITAL_SOURCE = "data/mock/maps/tool.gaode.poi_around.json"


def _clean_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list) and len(value) == 0:
            continue
        if isinstance(value, dict) and len(value) == 0:
            continue
        cleaned[key] = value
    return cleaned


def _safe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _infer_size_class(pet_weight: Optional[float]) -> Optional[str]:
    if pet_weight is None:
        return None
    if pet_weight <= 10:
        return "small"
    if pet_weight <= 25:
        return "medium"
    return "large"


def _build_user_profile(
    recognized_field_values: Dict[str, Any],
    memory_summary: Optional[Dict[str, Any]] = None,
) -> UserProfile:
    memory_summary = memory_summary or {}

    return UserProfile(
        preferred_pace=recognized_field_values.get("pace_preference") or memory_summary.get("preferred_pace"),
        attraction_preferences=recognized_field_values.get("preferred_categories")
        or memory_summary.get("attraction_preferences")
        or [],
        hotel_tier_preference=recognized_field_values.get("hotel_tier_preference")
        or memory_summary.get("hotel_tier_preference"),
    )


def _build_pet_profile(
    recognized_field_values: Dict[str, Any],
    memory_summary: Optional[Dict[str, Any]] = None,
) -> PetProfile:
    memory_summary = memory_summary or {}

    return PetProfile(
        pet_type=recognized_field_values.get("pet_type") or memory_summary.get("pet_type"),
        pet_breed=recognized_field_values.get("pet_breed") or memory_summary.get("pet_breed"),
        pet_age=recognized_field_values.get("pet_age") or memory_summary.get("pet_age"),
        pet_weight_kg=recognized_field_values.get("pet_weight_kg") or memory_summary.get("pet_weight_kg"),
        special_needs=_safe_list(
            recognized_field_values.get("pet_special_needs") or memory_summary.get("pet_special_needs")
        ),
        medical_history=memory_summary.get("pet_medical_history"),
        allergy_history=memory_summary.get("pet_allergy_history"),
        vaccination_status=memory_summary.get("vaccination_status"),
        commute_tolerance=memory_summary.get("commute_tolerance"),
        outdoor_tolerance=memory_summary.get("outdoor_tolerance"),
        stress_or_heat_risk=memory_summary.get("stress_or_heat_risk"),
    )


def _build_hard_rules(
    feature_id: FeatureIdEnum,
    recognized_field_values: Dict[str, Any],
    tool_results: Optional[Dict[str, Any]] = None,
) -> HardRules:
    tool_results = tool_results or {}
    pet_transport_rule_result = tool_results.get("pet_transport_rule_result") or {}

    hard_constraint_notes = [
        "Must follow official pet transport constraints.",
        "Must respect pet-friendly venue restrictions.",
        "Static transport and policy rule files are treated as the source of truth.",
    ]

    if pet_transport_rule_result:
        hard_constraint_notes.append("Pet transport rules attached in tool results.")

    if feature_id == FeatureIdEnum.TRAVEL_ROUTE_PLANNING:
        hard_constraint_notes.extend([
            "Must fit trip_days and daily_play_hours.",
            "Must respect transport preference when feasible.",
            "Must consider weather, operating hours, hotel distance, and route feasibility.",
        ])

    return HardRules(
        budget_cap=recognized_field_values.get("budget_total"),
        fixed_dates=[
            value
            for value in [
                recognized_field_values.get("travel_start_date"),
                recognized_field_values.get("travel_end_date"),
            ]
            if value
        ],
        hard_constraint_notes=hard_constraint_notes,
    )


def _build_live_context(
    recognized_field_values: Dict[str, Any],
    memory_summary: Optional[Dict[str, Any]] = None,
    tool_results: Optional[Dict[str, Any]] = None,
) -> LiveContext:
    memory_summary = memory_summary or {}
    tool_results = tool_results or {}

    weather_result = tool_results.get("weather_result") or memory_summary.get("current_weather")
    route_matrix_result = tool_results.get("route_matrix_result") or memory_summary.get("route_matrix_summary")

    return LiveContext(
        destination_city=recognized_field_values.get("destination_city"),
        travel_start_date=recognized_field_values.get("travel_start_date"),
        travel_end_date=recognized_field_values.get("travel_end_date"),
        trip_days=recognized_field_values.get("trip_days"),
        hotel_name=recognized_field_values.get("hotel_name"),
        hotel_area=recognized_field_values.get("hotel_area"),
        hotel_address=recognized_field_values.get("hotel_address"),
        daily_play_hours=recognized_field_values.get("daily_play_hours"),
        transport_preference=recognized_field_values.get("transport_preference"),
        budget_total=recognized_field_values.get("budget_total"),
        budget_per_person=recognized_field_values.get("budget_per_person"),
        target_pois=_safe_list(recognized_field_values.get("target_pois")),
        current_weather=weather_result,
        route_matrix_summary=route_matrix_result,
    )


def _build_soft_evidence(
    recognized_field_values: Dict[str, Any],
    memory_summary: Optional[Dict[str, Any]] = None,
    tool_results: Optional[Dict[str, Any]] = None,
) -> SoftEvidence:
    memory_summary = memory_summary or {}
    tool_results = tool_results or {}

    confidence_notes = [
        "Soft evidence should guide ranking, not override hard rules."
    ]

    historical_preferences = memory_summary.get("historical_preferences")
    if historical_preferences:
        confidence_notes.append(f"Historical preferences: {historical_preferences}")

    if tool_results.get("resource_status"):
        confidence_notes.append(f"Resource status: {tool_results['resource_status']}")

    return SoftEvidence(confidence_notes=confidence_notes)


def _build_constraint_summary(
    feature_id: FeatureIdEnum,
    recognized_field_values: Dict[str, Any],
    tool_results: Optional[Dict[str, Any]] = None,
) -> ConstraintSummary:
    tool_results = tool_results or {}

    weather_result = tool_results.get("weather_result") or {}
    pet_transport_rule_result = tool_results.get("pet_transport_rule_result") or {}
    opening_hours_summary = tool_results.get("opening_hours_summary") or {}
    hotel_distance_summary = tool_results.get("hotel_distance_summary") or {}
    pet_rule_result = tool_results.get("pet_rule_result") or {}

    risk_flags = []

    if recognized_field_values.get("pet_weight_kg") is None:
        risk_flags.append("missing_pet_weight")

    if recognized_field_values.get("travel_start_date") is None:
        risk_flags.append("missing_travel_start_date")

    if feature_id == FeatureIdEnum.TRAVEL_ROUTE_PLANNING:
        if not weather_result:
            risk_flags.append("weather_not_attached")
        if not pet_transport_rule_result and not pet_rule_result:
            risk_flags.append("transport_rules_not_attached")

    return ConstraintSummary(
        normalized_time_constraints=_clean_dict({
            "travel_start_date": recognized_field_values.get("travel_start_date"),
            "travel_end_date": recognized_field_values.get("travel_end_date"),
            "trip_days": recognized_field_values.get("trip_days"),
            "daily_play_hours": recognized_field_values.get("daily_play_hours"),
            "opening_hours_summary": opening_hours_summary,
        }),
        normalized_budget_constraints=_clean_dict({
            "budget_total": recognized_field_values.get("budget_total"),
            "budget_per_person": recognized_field_values.get("budget_per_person"),
        }),
        normalized_pet_constraints=_clean_dict({
            "pet_type": recognized_field_values.get("pet_type"),
            "pet_breed": recognized_field_values.get("pet_breed"),
            "pet_age": recognized_field_values.get("pet_age"),
            "pet_weight_kg": recognized_field_values.get("pet_weight_kg"),
            "pet_special_needs": recognized_field_values.get("pet_special_needs"),
            "pet_transport_rule_result": pet_transport_rule_result,
            "pet_rule_result": pet_rule_result,
        }),
        normalized_transport_constraints=_clean_dict({
            "transport_preference": recognized_field_values.get("transport_preference"),
            "hotel_distance_summary": hotel_distance_summary,
        }),
        normalized_weather_constraints=_clean_dict(weather_result),
        risk_flags=risk_flags,
    )


def _build_candidate_resource_summary(
    feature_id: FeatureIdEnum,
    tool_results: Optional[Dict[str, Any]] = None,
) -> CandidateResourceSummary:
    tool_results = tool_results or {}

    if feature_id == FeatureIdEnum.TRAVEL_ROUTE_PLANNING:
        return CandidateResourceSummary(
            candidate_spots=tool_results.get("candidate_spots", []),
            candidate_hotels=tool_results.get("candidate_hotels", []),
            candidate_pet_hospitals=tool_results.get("candidate_pet_hospitals", []),
            route_matrix_summary={
                "required_resources": [
                    "pet_transport_rule_db",
                    "weather_api",
                    "amap_geocode",
                    "amap_poi_search",
                    "amap_poi_detail",
                    "amap_route_matrix",
                ],
                "resource_status": tool_results.get("resource_status", "pending_or_mock"),
                "notes": "Planner packaging is ready; mock or live results may be attached here.",
                "route_matrix_result": tool_results.get("route_matrix_result", {}),
                "geocode_result": tool_results.get("geocode_result", {}),
            },
        )

    if feature_id == FeatureIdEnum.SCENIC_RECOMMENDATION:
        return CandidateResourceSummary(
            candidate_spots=tool_results.get("candidate_spots", []),
            route_matrix_summary={
                "required_resources": [
                    "amap_geocode",
                    "amap_poi_search",
                    "amap_poi_detail",
                    "review_tag_db",
                    "pet_friendly_rule_db",
                ],
                "resource_status": tool_results.get("resource_status", "pending_or_mock"),
                "notes": "Scenic recommendation depends on candidate spot retrieval and pet-friendly filtering.",
            },
        )

    if feature_id == FeatureIdEnum.DOCUMENT_MATERIAL_REMINDER:
        return CandidateResourceSummary(
            route_matrix_summary={
                "required_resources": [
                    "static_document_rule_db",
                ],
                "resource_status": tool_results.get("resource_status", "pending_or_mock"),
                "notes": "Document reminder depends on static rules.",
            },
        )

    return CandidateResourceSummary(
        route_matrix_summary={
            "required_resources": [],
            "resource_status": tool_results.get("resource_status", "unknown"),
            "notes": "No specific candidate resources mapped yet for this feature.",
        },
    )


def _build_required_output_format(feature_id: FeatureIdEnum) -> RequiredOutputFormat:
    if feature_id == FeatureIdEnum.TRAVEL_ROUTE_PLANNING:
        return RequiredOutputFormat(
            format_name="structured_json",
            must_include_fields=[
                "route_plan_options",
                "option_id",
                "option_summary",
                "daily_total_play_hours",
                "route_nodes",
                "route_legs",
                "estimated_total_cost",
                "route_reasoning",
                "constraint_notes",
            ],
        )

    if feature_id == FeatureIdEnum.DOCUMENT_MATERIAL_REMINDER:
        return RequiredOutputFormat(
            format_name="structured_json",
            must_include_fields=[
                "user_document_checklist",
                "pet_document_checklist",
                "optional_material_checklist",
                "compliance_notice",
                "predeparture_tips",
            ],
        )

    if feature_id == FeatureIdEnum.SCENIC_RECOMMENDATION:
        return RequiredOutputFormat(
            format_name="structured_json",
            must_include_fields=[
                "recommended_scenic_spots_by_category",
                "category_name",
                "scenic_spot_name",
                "scenic_type",
                "indoor_or_outdoor",
                "ticket_required",
                "ticket_price",
                "visitor_review_summary",
                "pet_friendly_evidence",
                "recommendation_reason",
            ],
        )

    return RequiredOutputFormat(
        format_name="structured_json",
        must_include_fields=[],
    )


def _build_context_summary_for_planner(
    feature_id: FeatureIdEnum,
    recognized_field_values: Dict[str, Any],
) -> Dict[str, Any]:
    return _clean_dict({
        "feature_id": feature_id.value,
        "destination_city": recognized_field_values.get("destination_city"),
        "trip_days": recognized_field_values.get("trip_days"),
        "pet_type": recognized_field_values.get("pet_type"),
        "pet_weight_kg": recognized_field_values.get("pet_weight_kg"),
        "transport_preference": recognized_field_values.get("transport_preference"),
        "budget_total": recognized_field_values.get("budget_total"),
        "planning_goal": "Build a safe, feasible, pet-friendly structured result.",
    })


def _build_evidence_blocks(
    recognized_field_values: Dict[str, Any],
    tool_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    tool_results = tool_results or {}

    pet_transport_rule_result = tool_results.get("pet_transport_rule_result") or {}
    pet_rule_result = tool_results.get("pet_rule_result") or {}
    weather_result = tool_results.get("weather_result") or {}
    route_matrix_result = tool_results.get("route_matrix_result") or {}
    candidate_spots = tool_results.get("candidate_spots") or []
    candidate_hotels = tool_results.get("candidate_hotels") or []
    candidate_pet_hospitals = tool_results.get("candidate_pet_hospitals") or []

    pet_weight = recognized_field_values.get("pet_weight_kg")
    pet_type = recognized_field_values.get("pet_type")
    pet_age = recognized_field_values.get("pet_age")
    pet_breed = recognized_field_values.get("pet_breed")
    size_class = _infer_size_class(pet_weight)

    evidence_blocks = {
        "transport_rule_result": {
            "source_type": "static",
            "source_name": STATIC_TRANSPORT_RULE_SOURCES,
            "status": "available" if (pet_transport_rule_result or pet_rule_result) else "missing",
            "summary": "Static transport and pet-policy feasibility constraints used for planner safety checks.",
            "data": _clean_dict({
                "pet_transport_rule_result": pet_transport_rule_result,
                "pet_rule_result": pet_rule_result,
            }),
        },
        "pet_profile_summary": {
            "source_type": "static",
            "source_name": f"{STATIC_PET_PROFILE_SOURCES} | recognized_field_values",
            "status": "available",
            "summary": "Core pet attributes grounded in normalized request fields and static pet profile datasets.",
            "data": _clean_dict({
                "pet_type": pet_type,
                "pet_breed": pet_breed,
                "pet_age": pet_age,
                "pet_weight_kg": pet_weight,
                "size_class": size_class,
            }),
        },
        "weather_constraint": {
            "source_type": "mock",
            "source_name": MOCK_WEATHER_SOURCE,
            "status": "available" if weather_result else "missing",
            "summary": "Mock weather constraint block for filtering unsafe outdoor planning.",
            "data": _clean_dict(weather_result) if isinstance(weather_result, dict) else weather_result,
        },
        "route_commute": {
            "source_type": "mock",
            "source_name": MOCK_ROUTE_SOURCE,
            "status": "available" if route_matrix_result else "missing",
            "summary": "Mock commute-time block for route feasibility and hotel-distance checks.",
            "data": _clean_dict(route_matrix_result) if isinstance(route_matrix_result, dict) else route_matrix_result,
        },
    }

    if candidate_spots:
        evidence_blocks["poi_candidates"] = {
            "source_type": "mock",
            "source_name": MOCK_POI_SOURCE,
            "status": "available",
            "summary": "Mock POI candidates retrieved from local Gaode sample outputs.",
            "data": candidate_spots,
        }

    if candidate_hotels:
        evidence_blocks["hotel_candidates"] = {
            "source_type": "mock",
            "source_name": MOCK_HOTEL_SOURCE,
            "status": "available",
            "summary": "Mock hotel candidate set for planner ranking and accommodation selection.",
            "data": candidate_hotels,
        }

    if candidate_pet_hospitals:
        evidence_blocks["pet_hospital_candidates"] = {
            "source_type": "mock",
            "source_name": MOCK_PET_HOSPITAL_SOURCE,
            "status": "available",
            "summary": "Mock nearby pet-hospital candidates from local POI samples.",
            "data": candidate_pet_hospitals,
        }

    return evidence_blocks


def _build_normalized_request_json(
    router_output: RouterOutput,
    current_user_message: str,
    memory_summary: Optional[Dict[str, Any]] = None,
    tool_results: Optional[Dict[str, Any]] = None,
) -> NormalizedRequestJson:
    recognized_field_values = router_output.recognized_field_values
    memory_summary = memory_summary or {}
    tool_results = tool_results or {}

    return NormalizedRequestJson(
        session_id=memory_summary.get("session_id"),
        raw_user_message=current_user_message,
        recognized_stage=router_output.recognized_stage,
        recognized_task=router_output.recognized_task,
        output_language=OutputLanguage.ZH,
        user_profile=_build_user_profile(recognized_field_values, memory_summary),
        pet_profile=_build_pet_profile(recognized_field_values, memory_summary),
        hard_rules=_build_hard_rules(
            router_output.recognized_task,
            recognized_field_values,
            tool_results,
        ),
        live_context=_build_live_context(
            recognized_field_values,
            memory_summary,
            tool_results,
        ),
        soft_evidence=_build_soft_evidence(
            recognized_field_values,
            memory_summary,
            tool_results,
        ),
    )


def build_planner_input(
    router_output: RouterOutput,
    current_user_message: str,
    memory_summary: Optional[Dict[str, Any]] = None,
    tool_results: Optional[Dict[str, Any]] = None,
) -> PlannerHandoffPayload:
    memory_summary = memory_summary or {}
    tool_results = tool_results or {}

    normalized_request_json = _build_normalized_request_json(
        router_output=router_output,
        current_user_message=current_user_message,
        memory_summary=memory_summary,
        tool_results=tool_results,
    )

    return PlannerHandoffPayload(
        normalized_request_json=normalized_request_json,
        constraint_summary=_build_constraint_summary(
            feature_id=router_output.recognized_task,
            recognized_field_values=router_output.recognized_field_values,
            tool_results=tool_results,
        ),
        candidate_resource_summary=_build_candidate_resource_summary(
            feature_id=router_output.recognized_task,
            tool_results=tool_results,
        ),
        required_output_format=_build_required_output_format(
            feature_id=router_output.recognized_task,
        ),
        context_summary_for_5_1_mini=_build_context_summary_for_planner(
            feature_id=router_output.recognized_task,
            recognized_field_values=router_output.recognized_field_values,
        ),
        evidence_blocks=_build_evidence_blocks(
            recognized_field_values=router_output.recognized_field_values,
            tool_results=tool_results,
        ),
    )


def is_ready_for_planner(router_output: RouterOutput) -> bool:
    return router_output.tool_invocation_decision == ToolInvocationDecision.READY_FOR_PLANNER