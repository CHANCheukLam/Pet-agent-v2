# app/tools.py

import json
from pathlib import Path
from config import MOCK_DATA_DIR

def load_mock(tool_filename: str) -> dict:
    path = MOCK_DATA_DIR / tool_filename
    if not path.exists():
        raise FileNotFoundError(f"Mock tool file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

def gaode_geocode(**kwargs):
    return load_mock("maps/tool.gaode.geocode.json")

def gaode_poi_search(**kwargs):
    return load_mock("maps/tool.gaode.poi_around.json")

def gaode_route_matrix(**kwargs):
    return load_mock("maps/tool.gaode.route_matrix.json")

def weather_forecast(**kwargs):
    return load_mock("weather/tool.qweather.forecast.json")

def gaode_poi_search(**kwargs):
    return load_mock("maps/tool.gaode.poi_around.json")