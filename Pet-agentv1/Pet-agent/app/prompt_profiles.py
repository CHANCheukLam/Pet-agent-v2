from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from config import BASE_DIR
from schemas import FeatureIdEnum, StageEnum


PROMPTS_DIR = BASE_DIR / "prompts"
DEFAULT_PROMPT_FILE = "agent_prompt2.yaml"


def _task_to_agent_id(stage: StageEnum, task: FeatureIdEnum) -> str:
    mapping: Dict[FeatureIdEnum, str] = {
        FeatureIdEnum.DOCUMENT_MATERIAL_REMINDER: "2",
        FeatureIdEnum.SCENIC_RECOMMENDATION: "3",
        FeatureIdEnum.TRAVEL_ROUTE_PLANNING: "4",
        FeatureIdEnum.HOTEL_NEARBY_PET_HOSPITAL_SUMMARY: "5",
        FeatureIdEnum.ROUTE_REPLANNING: "6",
        FeatureIdEnum.ALTERNATIVE_SCENIC_RECOMMENDATION: "7",
        FeatureIdEnum.NEARBY_HOSPITAL_RECOMMENDATION: "8",
        FeatureIdEnum.NEARBY_PET_HOSPITAL_RECOMMENDATION: "9",
    }

    if stage == StageEnum.GLOBAL:
        return "1"
    return mapping.get(task, "1")


def load_prompt_catalog(prompt_file_name: Optional[str] = None) -> Dict[str, Any]:
    file_name = (prompt_file_name or DEFAULT_PROMPT_FILE).strip() or DEFAULT_PROMPT_FILE
    prompt_path = PROMPTS_DIR / file_name
    if not prompt_path.exists():
        prompt_path = PROMPTS_DIR / DEFAULT_PROMPT_FILE

    if not prompt_path.exists():
        return {
            "version": "unknown",
            "name": "missing_prompt_file",
            "agents": {},
            "_meta": {
                "prompt_file": file_name,
                "prompt_path": str(prompt_path),
                "loaded": False,
            },
        }

    with prompt_path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}

    if not isinstance(payload, dict):
        payload = {}

    payload.setdefault("agents", {})
    payload["_meta"] = {
        "prompt_file": prompt_path.name,
        "prompt_path": str(prompt_path),
        "loaded": True,
    }
    return payload


def select_prompt_profile(
    *,
    recognized_stage: StageEnum,
    recognized_task: FeatureIdEnum,
    prompt_file_name: Optional[str] = None,
) -> Dict[str, Any]:
    catalog = load_prompt_catalog(prompt_file_name)
    agents = catalog.get("agents") or {}

    agent_id = _task_to_agent_id(recognized_stage, recognized_task)
    profile = agents.get(agent_id) or agents.get(int(agent_id)) or {}

    ordered_tools = profile.get("required_tools_order") or profile.get("allowed_tools") or []
    if not isinstance(ordered_tools, list):
        ordered_tools = []

    return {
        "prompt_file": (catalog.get("_meta") or {}).get("prompt_file", DEFAULT_PROMPT_FILE),
        "prompt_loaded": bool((catalog.get("_meta") or {}).get("loaded", False)),
        "agent_id": agent_id,
        "agent_name": str(profile.get("name") or ""),
        "agent_role": str(profile.get("role") or ""),
        "tool_order_preference": [str(item) for item in ordered_tools if item],
    }

