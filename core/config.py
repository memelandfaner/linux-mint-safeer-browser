#!/usr/bin/env python3
"""
Safeer Browser for Linux Mint - Configuration Manager
Manages user preferences, modular sidebar integrations, and virtual keyboard settings.
"""

import os
import json
import uuid
from typing import Dict, Any

CONFIG_DIR = os.path.expanduser("~/.config/safeer-mint")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "force_dark_mode": False,           # Prisili temni način na vseh spletnih straneh
    "theme": "midnight",                # "midnight", "mint", "neon", "amoled"
    "custom_css": "",                   # Lasten CSS slog uporabnika
    "user_scripts": [
        {
            "id": "sample_banner_cleaner",
            "name": "Primer: Konzola obvestilo",
            "pattern": "*",
            "code": "// Safeer Uporabniška skripta (Tampermonkey slog)\nconsole.log('🛡️ Safeer Custom Script teče na: ' + window.location.href);",
            "enabled": True,
            "run_at": "end"
        }
    ],
    "virtual_keyboard_enabled": False,  # Privzeto izklopljeno kot zahtevano
    "sidebar_enabled": True,            # Trajni vklop/izklop stranske vrstice
    "sidebar_width": 680,
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
            "url": "https://mail.google.com/mail/",
            "icon": "✉️",
            "enabled": True,
            "color": "#ea4335"
        }
    },
    "custom_portals": [
        {"title": "Xplore TV", "url": "https://www.xploretv.si/livetv", "color": "#e31837"},
        {"title": "YouTube", "url": "https://www.youtube.com", "color": "#cc0000"},
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
                    merged = DEFAULT_SETTINGS.copy()
                    merged.update(user_settings)
                    # If youtube was previously in integrations, remove it as requested
                    if "integrations" in merged and "youtube" in merged["integrations"]:
                        del merged["integrations"]["youtube"]
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

    def toggle_force_dark(self) -> bool:
        """Trajno vklopi ali izklopi prisilni temni način za vse spletne strani."""
        cur = self.settings.get("force_dark_mode", False)
        self.settings["force_dark_mode"] = not cur
        self.save_settings()
        return not cur

    def toggle_sidebar_permanent(self) -> bool:
        """Trajno vklopi ali izklopi prikaz stranske vrstice."""
        cur = self.settings.get("sidebar_enabled", True)
        self.settings["sidebar_enabled"] = not cur
        self.save_settings()
        return not cur

    def toggle_integration(self, integration_id: str) -> bool:
        if "integrations" in self.settings and integration_id in self.settings["integrations"]:
            cur = self.settings["integrations"][integration_id].get("enabled", True)
            self.settings["integrations"][integration_id]["enabled"] = not cur
            self.save_settings()
            return not cur
        return False

    def add_integration(self, name: str, url: str, icon: str = "🌐") -> str:
        """Doda poljubno novo spletno stran v stransko orodno vrstico."""
        if not name or not url:
            return ""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        item_id = "custom_" + str(uuid.uuid4())[:8]
        if "integrations" not in self.settings:
            self.settings["integrations"] = {}

        self.settings["integrations"][item_id] = {
            "name": name.strip(),
            "url": url.strip(),
            "icon": icon.strip() if icon.strip() else "🌐",
            "enabled": True,
            "color": "#00d2ff"
        }
        self.save_settings()
        return item_id

    def remove_integration(self, integration_id: str) -> bool:
        """Odstrani spletno stran iz stranske orodne vrstice."""
        if "integrations" in self.settings and integration_id in self.settings["integrations"]:
            del self.settings["integrations"][integration_id]
            self.save_settings()
            return True
        return False

    def get_user_scripts(self):
        """Vrne seznam vseh uporabniških skript."""
        return self.settings.get("user_scripts", [])

    def save_user_scripts(self, scripts):
        """Shrani posodobljen seznam uporabniških skript."""
        self.settings["user_scripts"] = scripts
        self.save_settings()

    def add_user_script(self, name: str, pattern: str, code: str, run_at: str = "end") -> str:
        """Doda novo uporabniško skripto (Greasemonkey slog)."""
        script_id = "script_" + str(uuid.uuid4())[:8]
        new_script = {
            "id": script_id,
            "name": name.strip() or "Brez imena",
            "pattern": pattern.strip() or "*",
            "code": code,
            "enabled": True,
            "run_at": run_at
        }
        scripts = self.get_user_scripts()
        scripts.append(new_script)
        self.save_user_scripts(scripts)
        return script_id

    def update_user_script(self, script_id: str, name: str, pattern: str, code: str, enabled: bool, run_at: str = "end") -> bool:
        """Posodobi obstoječo uporabniško skripto."""
        scripts = self.get_user_scripts()
        for s in scripts:
            if s["id"] == script_id:
                s["name"] = name.strip()
                s["pattern"] = pattern.strip()
                s["code"] = code
                s["enabled"] = enabled
                s["run_at"] = run_at
                self.save_user_scripts(scripts)
                return True
        return False

    def delete_user_script(self, script_id: str) -> bool:
        """Izbriše uporabniško skripto."""
        scripts = self.get_user_scripts()
        new_scripts = [s for s in scripts if s["id"] != script_id]
        if len(new_scripts) != len(scripts):
            self.save_user_scripts(new_scripts)
            return True
        return False

    def toggle_user_script(self, script_id: str) -> bool:
        """Vklopi ali izklopi uporabniško skripto."""
        scripts = self.get_user_scripts()
        for s in scripts:
            if s["id"] == script_id:
                s["enabled"] = not s.get("enabled", True)
                self.save_user_scripts(scripts)
                return s["enabled"]
        return False

