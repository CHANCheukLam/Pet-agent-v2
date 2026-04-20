# app/config.py

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# MODE
RUN_MODE = os.getenv("RUN_MODE", "mock")  # mock | real

# MODEL CONFIG (string only, no SDK yet)
MODEL_4MINI = "gpt-4.1-mini"
MODEL_5MINI = "gpt-5.1-mini"

# DATA PATHS
DATA_DIR = BASE_DIR / "data"
STATIC_DATA_DIR = DATA_DIR / "static"
MOCK_DATA_DIR = DATA_DIR / "mock"

# FEATURE FLAGS
ENABLE_IN_TRIP = True
ENABLE_WEATHER = True
ENABLE_SOCIAL_KNOWLEDGE = True
