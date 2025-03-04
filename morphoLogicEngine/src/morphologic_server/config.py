"""Config module loading settings from JSON file."""
import os
import json

from pathlib import Path

def load_settings():
    """
    Loads global settings from JSON file.
    Raises FileNotFoundError if file is missing.
    """
    settings_path = Path(__file__).resolve().parents[2] / "config/settings.json"
    if not os.path.exists(settings_path):
        raise FileNotFoundError("Settings file not found.")

    with open(settings_path, "r", encoding="utf-8") as f:
        return json.load(f)

settings = load_settings()
