"""
NOTE (April 2026):
This file contains illustrative smoke tests expressing expected
high‑level agent behaviors (routing, blocking, planner invocation).

Authoritative evaluation artifacts are located in:
tests/golden_samples/ and tests/golden_samples/manifest.json.

These smoke tests are not part of the formal evaluation pipeline.
"""

import importlib.util
import sys
from pathlib import Path

# -------------------------
# Dynamic import of app/main.py
# -------------------------

APP_DIR = Path(__file__).resolve().parents[1] / "app"
MAIN_PATH = APP_DIR / "main.py"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "tests" / "outputs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

spec = importlib.util.spec_from_file_location("main", MAIN_PATH)
assert spec is not None
assert spec.loader is not None

main = importlib.util.module_from_spec(spec)
sys.modules["main"] = main
spec.loader.exec_module(main)


# -------------------------
# Helper
# -------------------------

def run_and_save(case_name: str, message: str):
    """
    Runs one evaluation case and saves output for inspection.
    """
    return main.run_once(
        message,
        save_path=str(OUTPUT_DIR / f"{case_name}.json"),
    )


# -------------------------
# Tests
# -------------------------

def test_complete_route_request_ready_for_planner():
    msg = (
        "Plan a 2 day trip to Shanghai on 2026-05-01 with my dog, "
        "3 years old, 8 kg, 6 hours per day, by taxi."
    )
    result = run_and_save("01_complete_route", msg)

    assert result["status"] == "ready_for_planner"
    assert result["planner_invoked"] is True

    planner_input = result["planner_input"]
    req = planner_input["normalized_request_json"]

    assert req["recognized_stage"] == "pre_trip"
    assert req["recognized_task"] == "travel_route_planning"

    assert req["live_context"]["destination_city"] == "Shanghai"
    assert req["live_context"]["travel_start_date"] == "2026-05-01"
    assert req["live_context"]["trip_days"] == 2
    assert req["live_context"]["daily_play_hours"] == 6.0
    assert req["live_context"]["transport_preference"] == "taxi"

    assert req["pet_profile"]["pet_type"] == "dog"
    assert req["pet_profile"]["pet_age"] == 3.0
    assert req["pet_profile"]["pet_weight_kg"] == 8.0


def test_incomplete_route_request_needs_more_info():
    msg = "Plan a trip to Shanghai with my dog."
    result = run_and_save("02_missing_fields", msg)

    assert result["status"] == "need_more_info"
    assert result["planner_invoked"] is False
    assert result["recognized_stage"] == "pre_trip"
    assert result["recognized_task"] == "travel_route_planning"

    missing = result["missing_fields_resolution_status"]
    assert missing["is_complete"] is False

    for field in [
        "travel_start_date",
        "trip_days",
        "daily_play_hours",
        "transport_preference",
        "pet_age",
        "pet_weight_kg",
    ]:
        assert field in missing["missing_required_fields"]


def test_route_planning_has_mock_constraints_attached():
    msg = (
        "I want a 3-day pet-friendly trip to Shanghai starting on 2026-05-10. "
        "I want to spend 6 hours per day sightseeing, prefer taxi for transport, "
        "and I will travel with my 3-year-old dog that weighs 8 kg."
    )
    result = run_and_save("03_constraints_attached", msg)

    assert result["status"] == "ready_for_planner"
    assert result["planner_invoked"] is True

    planner_input = result["planner_input"]
    constraint_summary = planner_input["constraint_summary"]
    candidate_resource_summary = planner_input["candidate_resource_summary"]

    assert constraint_summary["normalized_weather_constraints"] != {}
    assert "pet_transport_rule_result" in constraint_summary["normalized_pet_constraints"]
    assert "pet_rule_result" in constraint_summary["normalized_pet_constraints"]
    assert constraint_summary["risk_flags"] == []

    assert candidate_resource_summary["route_matrix_summary"]["resource_status"] == "mock_attached"


def test_document_request_validated_but_not_planner_routed():
    msg = "What documents do I need to travel to Shanghai with my cat?"
    result = run_and_save("04_document_request", msg)

    assert result["status"] == "validated_but_not_planner_routed"
    assert result["planner_invoked"] is False
    assert result["recognized_stage"] == "pre_trip"
    assert result["recognized_task"] == "document_material_reminder"

    stub = result["structured_task_stub_json"]
    assert stub["recognized_field_values"]["destination_city"] == "Shanghai"
    assert stub["recognized_field_values"]["pet_type"] == "cat"


def test_scenic_recommendation_route_is_detected():
    msg = "Recommend scenic spots in Beijing for my dog, 2 years old, 6 kg."
    result = run_and_save("05_scenic_detected", msg)

    assert result["recognized_stage"] == "pre_trip"
    assert result["recognized_task"] == "scenic_recommendation"


def test_route_replanning_detected_as_in_trip():
    msg = "I am near the Bund right now, please replan my route because of traffic."
    result = run_and_save("06_route_replan", msg)

    assert result["recognized_stage"] == "in_trip"
    assert result["recognized_task"] == "route_replanning"


def test_nearby_pet_hospital_detected_as_in_trip():
    msg = "I need a nearby pet hospital right now for my dog."
    result = run_and_save("07_pet_hospital", msg)

    assert result["recognized_stage"] == "in_trip"
    assert result["recognized_task"] == "nearby_pet_hospital_recommendation"


def test_invalid_numeric_like_text_falls_back_safely():
    msg = (
        "Plan a trip to Shanghai on 2026-05-01 with my dog, "
        "three years old, eight kg, six hours per day, taxi."
    )
    result = run_and_save("08_invalid_numeric", msg)

    assert result["recognized_stage"] == "pre_trip"
    assert result["recognized_task"] == "travel_route_planning"
    assert result["status"] in {"need_more_info", "ready_for_planner"}

    if result["status"] == "need_more_info":
        assert result["planner_invoked"] is False
        assert result["missing_fields_resolution_status"]["is_complete"] is False