"""
Dev helper script: run the 4.1-mini router in isolation for a single message.
Not part of the production agent; used for Task 4 router-only verification.
"""
import json
from router import route_user_message


def _to_jsonable(payload):
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")
    return payload


def router_only(user_message: str):
    memory_summary = {
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

    router_output = route_user_message(
        current_user_message=user_message,
        memory_summary=memory_summary,
    )

    output = {
        "recognized_stage": router_output.recognized_stage.value,
        "recognized_task": router_output.recognized_task.value,
        "recognized_field_values": _to_jsonable(router_output.recognized_field_values),
        "missing_fields_resolution_status": _to_jsonable(router_output.missing_fields_resolution_status),
        "structured_task_stub_json": _to_jsonable(router_output.structured_task_stub_json),
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    router_only("我想在2026-04-25带一只3岁的35公斤大狗从北京去上海玩2天，每天玩6小时，尽量轻松一点，打车和公共交通都可以。")