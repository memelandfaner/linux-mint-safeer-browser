#!/usr/bin/env python3
"""
Safeer Browser for Linux Mint - Configuration Manager
Manages user preferences, sidebar integrations, and virtual keyboard settings.
"""

import os
import json
from typing import Dict, Any

CONFIG_DIR = os.path.expanduser("~/.config/safeer-mint")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "virtual_keyboard_enabled": False,  # Privzeto izklopljeno kot zahtevano
    "sidebar_enabled": True,
    "sidebar_width": 420,
    "search_engine": "google",
    "adblock_enabled": True,
    "homepage": "safeer://home",
    "integrations": {
        "messenger": {
            "name": "Facebook Messenger",
            "url": "https://www.messenger.com",
            "icon": "💬",
            "enabled": True,
            "color": "#0084ff"
        },
        "gmail": {
            "name": "Gmail",
            "url": "https://mail.google.com",
            "icon": "✉️",
            "enabled": True,
            "color": "#ea4335"
        },
        "youtube": {
            "name": "YouTube",
            "url": "https://www.youtube.com",
            "icon": "📺",
            "enabled": True,
            "color": "#ff0000"
        }
    },
    "custom_portals": [
        {"title": "Xplore TV", "url": "https://www.xploretv.si/livetv", "color": "#e31837"},
        {"title": "24ur.com", "url": "https://www.24ur.com", "color": "#1256a8"},
        {"title": "RTV SLO", "url": "https://www.rtvslo.si", "color": "#0284c7"},
        {"title": "Filmi", "url": "https://hydrahd.ws/", "color": "#0277a3"},
        {"title": "ChatGPT", "url": "https://chatgpt.com", "color": "#10a37f"},
        {"title": "CryptoQuant", "url": "https://cryptoquant.com", "color": "#f59e0b"}
    ]
}


class ConfigManager:
    def __init__(self):
        self.config_dir = CONFIG_DIR
        self.config_file = CONFIG_FILE
        self.settings = self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_dir):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
            except Exception as e:
                print(f"[Config] Napaka pri ustvarjanju mape: {e}")

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    user_settings = json.load(f)
                    # Merge with defaults
                    merged = DEFAULT_SETTINGS.copy()
                    merged.update(user_settings)
                    return merged
            except Exception as e:
                print(f"[Config] Napaka pri branju nastavitev: {e}")

        self.save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    def save_settings(self, settings: Dict[str, Any] = None) -> bool:
        if settings is not None:
            self.settings = settings
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[Config] Napaka pri shranjevanju: {e}")
            return False

    def get(self, key: str, default=None):
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        self.settings[key] = value
        return self.save_settings()

    def toggle_virtual_keyboard(self) -> bool:
        new_state = not self.settings.get("virtual_keyboard_enabled", False)
        self.settings["virtual_keyboard_enabled"] = new_state
        self.save_settings()
        return new_state

    def toggle_integration(self, integration_id: str) -> bool:
        if "integrations" in self.settings and integration_id in self.settings["integrations"]:
            cur = self.settings["integrations"][integration_id].get("enabled", True)
            self.settings["integrations"][integration_id]["enabled"] = not cur
            self.save_settings()
            return not cur
        return False
