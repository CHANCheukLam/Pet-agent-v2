from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StageEnum(str, Enum):
    GLOBAL = "global"
    PRE_TRIP = "pre_trip"
    IN_TRIP = "in_trip"


class FeatureIdEnum(str, Enum):
    WELCOME_AND_STAGE_DETECTION = "welcome_and_stage_detection"
    DOCUMENT_MATERIAL_REMINDER = "document_material_reminder"
    SCENIC_RECOMMENDATION = "scenic_recommendation"
    TRAVEL_ROUTE_PLANNING = "travel_route_planning"
    HOTEL_NEARBY_PET_HOSPITAL_SUMMARY = "hotel_nearby_pet_hospital_summary"
    ROUTE_REPLANNING = "route_replanning"
    ALTERNATIVE_SCENIC_RECOMMENDATION = "alternative_scenic_recommendation"
    NEARBY_HOSPITAL_RECOMMENDATION = "nearby_hospital_recommendation"
    NEARBY_PET_HOSPITAL_RECOMMENDATION = "nearby_pet_hospital_recommendation"


class ToolInvocationDecision(str, Enum):
    NO_TOOL_NEEDED = "no_tool_needed"
    TOOL_NEEDED = "tool_needed"
    READY_FOR_PLANNER = "ready_for_planner"
    BLOCKED_BY_MISSING_FIELDS = "blocked_by_missing_fields"


class OutputLanguage(str, Enum):
    ZH = "zh"
    EN = "en"
    BILINGUAL = "bilingual"


class UserProfile(BaseModel):
    user_age: Optional[int] = None
    traveler_count: Optional[int] = None
    medical_history: Optional[str] = None
    dietary_restrictions: Optional[str] = None
    preferred_pace: Optional[str] = None
    attraction_preferences: List[str] = Field(default_factory=list)
    hotel_tier_preference: Optional[str] = None


class PetProfile(BaseModel):
    pet_type: Optional[str] = None
    pet_breed: Optional[str] = None
    pet_age: Optional[float] = None
    pet_weight_kg: Optional[float] = None
    pet_sex: Optional[str] = None
    neutered: Optional[bool] = None
    vaccination_status: Optional[str] = None
    allergy_history: Optional[str] = None
    medical_history: Optional[str] = None
    special_needs: List[str] = Field(default_factory=list)
    commute_tolerance: Optional[str] = None
    outdoor_tolerance: Optional[str] = None
    stress_or_heat_risk: Optional[str] = None


class HardRules(BaseModel):
    transport_rules: List[Dict[str, Any]] = Field(default_factory=list)
    venue_rules: List[Dict[str, Any]] = Field(default_factory=list)
    budget_cap: Optional[float] = None
    fixed_dates: List[str] = Field(default_factory=list)
    hard_constraint_notes: List[str] = Field(default_factory=list)


class LiveContext(BaseModel):
    destination_city: Optional[str] = None
    travel_start_date: Optional[str] = None
    travel_end_date: Optional[str] = None
    trip_days: Optional[int] = None
    hotel_name: Optional[str] = None
    hotel_area: Optional[str] = None
    hotel_address: Optional[str] = None
    daily_play_hours: Optional[float] = None
    transport_preference: Optional[str] = None
    budget_total: Optional[float] = None
    budget_per_person: Optional[float] = None
    current_weather: Optional[Dict[str, Any]] = None
    route_matrix_summary: Optional[Dict[str, Any]] = None
    target_pois: List[str] = Field(default_factory=list)


class SoftEvidence(BaseModel):
    social_reviews: List[Dict[str, Any]] = Field(default_factory=list)
    pet_friendly_tags: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_notes: List[str] = Field(default_factory=list)


class NormalizedRequestJson(BaseModel):
    session_id: Optional[str] = None
    raw_user_message: str
    recognized_stage: StageEnum
    recognized_task: FeatureIdEnum
    output_language: OutputLanguage = OutputLanguage.ZH

    user_profile: UserProfile = Field(default_factory=UserProfile)
    pet_profile: PetProfile = Field(default_factory=PetProfile)
    hard_rules: HardRules = Field(default_factory=HardRules)
    live_context: LiveContext = Field(default_factory=LiveContext)
    soft_evidence: SoftEvidence = Field(default_factory=SoftEvidence)


class MissingFieldsResolutionStatus(BaseModel):
    is_complete: bool
    missing_required_fields: List[str] = Field(default_factory=list)
    blocking_fields: List[str] = Field(default_factory=list)
    follow_up_question: Optional[str] = None


class ConstraintSummary(BaseModel):
    normalized_time_constraints: Dict[str, Any] = Field(default_factory=dict)
    normalized_budget_constraints: Dict[str, Any] = Field(default_factory=dict)
    normalized_pet_constraints: Dict[str, Any] = Field(default_factory=dict)
    normalized_transport_constraints: Dict[str, Any] = Field(default_factory=dict)
    normalized_weather_constraints: Dict[str, Any] = Field(default_factory=dict)
    risk_flags: List[str] = Field(default_factory=list)


class CandidateResourceSummary(BaseModel):
    candidate_spots: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_hotels: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_pet_hospitals: List[Dict[str, Any]] = Field(default_factory=list)
    route_matrix_summary: Dict[str, Any] = Field(default_factory=dict)


class RequiredOutputFormat(BaseModel):
    format_name: str = "structured_json"
    must_include_fields: List[str] = Field(default_factory=list)


class StructuredTaskStubJson(BaseModel):
    recognized_stage: StageEnum
    recognized_task: FeatureIdEnum
    recognized_field_values: Dict[str, Any] = Field(default_factory=dict)


class RouterOutput(BaseModel):
    recognized_stage: StageEnum
    recognized_task: FeatureIdEnum
    recognized_field_values: Dict[str, Any] = Field(default_factory=dict)
    missing_fields_resolution_status: MissingFieldsResolutionStatus
    tool_invocation_decision: ToolInvocationDecision
    structured_task_stub_json: StructuredTaskStubJson


class PlannerHandoffPayload(BaseModel):
    normalized_request_json: NormalizedRequestJson
    constraint_summary: ConstraintSummary
    candidate_resource_summary: CandidateResourceSummary
    required_output_format: RequiredOutputFormat
    context_summary_for_5_1_mini: Dict[str, Any]
    evidence_blocks: Dict[str, Any] = {}


class RouteLeg(BaseModel):
    from_node: str
    to_node: str
    transport_mode: str
    commute_duration_minutes: int


class RouteNode(BaseModel):
    day_index: int
    scenic_order: int
    scenic_name: str
    planned_stay_duration_minutes: int


class RoutePlanOption(BaseModel):
    option_id: str
    option_summary: str
    daily_total_play_hours: float
    route_nodes: List[RouteNode] = Field(default_factory=list)
    route_legs: List[RouteLeg] = Field(default_factory=list)
    estimated_total_cost: Optional[float] = None
    route_reasoning: Optional[str] = None
    constraint_notes: List[str] = Field(default_factory=list)


class PlannerStructuredOutput(BaseModel):
    route_plan_options: List[RoutePlanOption] = Field(default_factory=list)
    reasoning_summary: Optional[str] = None
    constraint_satisfaction_notes: List[str] = Field(default_factory=list)