from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from planner import build_planner_input
from router import route_user_message

"""
main.py

Execution modes:

1) Default (python app/main.py):
   - Deterministic Phase‑2 evaluation harness
   - Generates tests/golden_samples/*.json and manifest.json
   - Official entry point for Member 3 evaluation

2) Optional REPL (python app/main.py --repl):
   - Interactive Pre‑Trip Agent simulation
   - Demonstrates multi‑turn field completion
   - Uses the same router + planner logic

Evaluation is intentionally the default mode.
"""

# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "tests" / "golden_samples"

# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------

def _to_jsonable(payload: Any) -> Any:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return payload


def _maybe_save_output(save_path: Optional[str], payload: Dict[str, Any]) -> None:
    if not save_path:
        return
    path = Path(save_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _detect_input_language(text: str) -> str:
    return "zh" if any("\u4e00" <= ch <= "\u9fff" for ch in text) else "en"


def _build_source_provenance(tool_results: Dict[str, Any]) -> Dict[str, str]:
    tool_results = tool_results or {}
    return {
        "pet_breed_database": "static",
        "policy_rules": "static",
        "agents_md_logic": "static",
        "pet_rules": "static"
        if tool_results.get("pet_rule_result")
        or tool_results.get("pet_transport_rule_result")
        else "none",
        "weather": "mock" if tool_results.get("weather_result") else "none",
        "route_matrix": "mock" if tool_results.get("route_matrix_result") else "none",
        "gaode_poi": "mock" if tool_results.get("candidate_spots") else "none",
        "hotel_candidates": "mock" if tool_results.get("candidate_hotels") else "none",
        "pet_hospital_candidates": "mock" if tool_results.get("candidate_pet_hospitals") else "none",
    }

# ---------------------------------------------------------
# Mock memory & tool layers (Phase 2)
# ---------------------------------------------------------

def _mock_memory_summary() -> Dict[str, Any]:
    return {
        "session_id": "demo-session-001",
        "destination_city": None,
        "travel_start_date": None,
        "travel_end_date": None,
        "trip_days": None,
        "daily_play_hours": None,
        "transport_preference": None,
        "budget_total": None,
        "budget_per_person": None,
        "pet_type": None,
        "pet_age": None,
        "pet_weight_kg": None,
        "historical_preferences": None,
        "current_weather": None,
        "route_matrix_summary": None,
    }


def _update_memory_from_router(memory: Dict[str, Any], router_output: Any) -> None:
    """
    Merge non‑null recognized fields into memory.
    Enables proper multi‑turn Agent behavior.
    """
    for key, value in router_output.recognized_field_values.items():
        if value is not None:
            memory[key] = value


def _mock_tool_results() -> Dict[str, Any]:
    return {
        "weather_result": {
            "forecast_days": [
                {
                    "date": "2026-07-20",
                    "condition": "hot",
                    "temperature_c": 36,
                    "outdoor_suitability": "low",
                }
            ],
            "planning_note": "High heat expected; reduce outdoor activity.",
        },
        "route_matrix_result": {
            "hotel_to_spot_avg_minutes": 25,
            "spot_to_spot_avg_minutes": 20,
            "longest_leg_minutes": 40,
            "transport_mode_used_for_estimate": "taxi",
        },
        "pet_transport_rule_result": {
            "taxi": "allowed_if_driver_accepts_or_if_carrier_used",
            "public_transport": "restricted",
        },
        "pet_rule_result": {
            "heat_risk": "high",
            "max_continuous_outdoor_minutes": 60,
        },
        "candidate_spots": [{"name": "Indoor Museum"}],
        "candidate_hotels": [],
        "candidate_pet_hospitals": [],
    }


def _mock_tool_results_no_dynamic() -> Dict[str, Any]:
    return {
        "pet_transport_rule_result": {
            "taxi": "allowed_if_driver_accepts_or_if_carrier_used"
        },
        "pet_rule_result": {
            "heat_risk": "medium"
        },
        "candidate_spots": [],
        "candidate_hotels": [],
        "candidate_pet_hospitals": [],
    }

# ---------------------------------------------------------
# Evaluation output builder
# ---------------------------------------------------------

def _build_evaluation_output(
    *,
    input_case_id: str,
    user_message: str,
    router_output: Any,
    tool_results: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "input_case_id": input_case_id,
        "raw_user_message": user_message,
        "input_language": _detect_input_language(user_message),
        "recognized_stage": router_output.recognized_stage.value,
        "recognized_task": router_output.recognized_task.value,
        "recognized_field_values": _to_jsonable(router_output.recognized_field_values),
        "missing_fields_resolution_status": _to_jsonable(
            router_output.missing_fields_resolution_status
        ),
        "source_provenance": _build_source_provenance(tool_results),
        "planning_status": None,
        "planner_result": None,
        "fallback_or_block_reason": None,
    }

# ---------------------------------------------------------
# Single evaluation run
# ---------------------------------------------------------

def run_once(
    *,
    user_message: str,
    tool_results: Dict[str, Any],
    input_case_id: str,
    save_path: str,
) -> Dict[str, Any]:
    memory = _mock_memory_summary()

    router_output = route_user_message(
        current_user_message=user_message,
        memory_summary=memory,
    )

    output = _build_evaluation_output(
        input_case_id=input_case_id,
        user_message=user_message,
        router_output=router_output,
        tool_results=tool_results,
    )

    validation = router_output.missing_fields_resolution_status
    fields = output["recognized_field_values"]

    if not validation.is_complete:
        output["planning_status"] = "blocked_incomplete_context"
        output["fallback_or_block_reason"] = "Missing required route-planning fields."
        _maybe_save_output(save_path, output)
        return output

    if fields.get("pet_type") == "dog" and fields.get("pet_weight_kg", 0) >= 30:
        output["planning_status"] = "blocked_hard_constraint"
        output["fallback_or_block_reason"] = "Pet weight exceeds safe transport limits."
        _maybe_save_output(save_path, output)
        return output

    planner_input = build_planner_input(
        router_output=router_output,
        current_user_message=user_message,
        memory_summary=memory,
        tool_results=tool_results,
    )

    output["planning_status"] = "success"
    output["planner_result"] = {
        "planner_input": planner_input.model_dump(mode="json")
    }
    _maybe_save_output(save_path, output)
    return output

# ---------------------------------------------------------
# Evaluation suite (default)
# ---------------------------------------------------------

def run_evaluation_suite() -> List[Dict[str, Any]]:
    cases = [
        {
            "case_id": "case_001_cn_happy",
            "message": "我想在2026-05-10带一只3岁的8公斤狗从北京去上海玩3天，每天游玩6小时，预算3000元，打车出行。",
            "tool_results": _mock_tool_results(),
        },
        {
            "case_id": "case_002_en_happy",
            "message": "I want to take my 3-year-old 8kg dog from Beijing to Shanghai for a 3-day trip starting on 2026-05-10, spending 6 hours per day sightseeing, budget 3000 RMB, and prefer taxi.",
            "tool_results": _mock_tool_results(),
        },
        {
            "case_id": "case_003_hard_block",
            "message": "我想在2026-05-10带一只5岁的35公斤大狗从北京去上海玩2天，每天游玩6小时，打车出行。",
            "tool_results": _mock_tool_results(),
        },
        {
            "case_id": "case_004_missing_fields",
            "message": "我想带狗去上海玩",
            "tool_results": _mock_tool_results(),
        },
        {
            "case_id": "case_005_fallback_static_only",
            "message": "我想在2026-05-10带一只3岁的8公斤狗从北京去上海玩2天，每天游玩5小时，打车出行。",
            "tool_results": _mock_tool_results_no_dynamic(),
        },
        {
            "case_id": "case_006_weather_mock",
            "message": "我想在2026-07-20带一只3岁的10公斤狗从北京去上海玩3天，每天游玩6小时，主要安排户外景点，打车出行。",
            "tool_results": _mock_tool_results(),
        },
    ]

    results: List[Dict[str, Any]] = []
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for case in cases:
        result = run_once(
            user_message=case["message"],
            tool_results=case["tool_results"],
            input_case_id=case["case_id"],
            save_path=str(OUTPUT_DIR / f"{case['case_id']}.json"),
        )
        results.append(result)

    with (OUTPUT_DIR / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results

# ---------------------------------------------------------
# Interactive REPL (agent mode)
# ---------------------------------------------------------

def repl() -> None:
    print("Pet-Agent Pre-Trip REPL")
    print("Type 'exit' or 'quit' to end.\n")

    memory = _mock_memory_summary()

    while True:
        user_message = input("User: ").strip()
        if user_message.lower() in {"exit", "quit"}:
            print("Goodbye")
            break

        router_output = route_user_message(
            current_user_message=user_message,
            memory_summary=memory,
        )

        _update_memory_from_router(memory, router_output)

        print("\n[Router Output]")
        print(json.dumps(_to_jsonable(router_output), ensure_ascii=False, indent=2))

        resolution = router_output.missing_fields_resolution_status
        if not resolution.is_complete:
            if resolution.follow_up_question:
                print("\nAgent:", resolution.follow_up_question)
            continue

        fields = router_output.recognized_field_values
        if fields.get("pet_type") == "dog" and fields.get("pet_weight_kg", 0) >= 30:
            print("\nAgent: 抱歉，当前宠物体重已超过安全运输限制，无法继续规划。")
            continue

        planner_input = build_planner_input(
            router_output=router_output,
            current_user_message=user_message,
            memory_summary=memory,
            tool_results=_mock_tool_results(),
        )

        print("\n[Planner Input]")
        print(json.dumps(planner_input.model_dump(mode="json"), ensure_ascii=False, indent=2))

# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    if "--repl" in sys.argv:
        repl()
    else:
        run_evaluation_suite()