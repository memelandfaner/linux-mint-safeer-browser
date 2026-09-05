#!/usr/bin/env python3
"""
Safeer Browser - 1-Click Bookmarks & Portals Importer
Parses standard Netscape Bookmark HTML files exported from Firefox, Chrome, Chromium, Brave, Edge, Opera, etc.
"""

from html.parser import HTMLParser
import glob
import json
import os
import re
import shutil
import sqlite3
import tempfile
import urllib.parse
from typing import List, Dict, Any, Tuple, Optional


def guess_icon_for_url(url: str, title: str) -> str:
    """Guess an appropriate emoji icon based on URL and title."""
    target = f"{url} {title}".lower()
    if "music.youtube" in target or "spotify" in target or "soundcloud" in target or "glasb" in target or "music" in target:
        return "🎵"
    if "youtube.com" in target or "youtu.be" in target:
        return "▶️"
    if "github" in target or "gitlab" in target:
        return "🐙"
    if "reddit" in target:
        return "🤖"
    if "twitter" in target or "x.com" in target or "mastodon" in target or "threads" in target:
        return "🐦"
    if "facebook" in target or "messenger" in target:
        return "💬"
    if "mail" in target or "gmail" in target or "outlook" in target or "proton" in target:
        return "✉️"
    if "rtvslo" in target or "24ur" in target or "delo" in target or "dnevnik" in target or "news" in target:
        return "📰"
    if "tv" in target or "xplore" in target or "netflix" in target or "film" in target or "stream" in target:
        return "📺"
    if "crypto" in target or "binance" in target or "bitcoin" in target or "finance" in target:
        return "📊"
    if "chatgpt" in target or "claude" in target or "openai" in target or "perplexity" in target or "ai" in target:
        return "🤖"
    if "shop" in target or "amazon" in target or "mimovrste" in target or "bolha" in target or "ebay" in target:
        return "🛒"
    if "wiki" in target or "dokument" in target:
        return "📚"
    return "🌐"


def guess_color_for_icon(icon: str) -> str:
    """Generate a vibrant color accent based on icon category."""
    color_map = {
        "▶️": "#cc0000",
        "🎵": "#a855f7",
        "🐙": "#24292e",
        "🤖": "#10a37f",
        "🐦": "#0284c7",
        "💬": "#0084ff",
        "✉️": "#ea4335",
        "📰": "#1256a8",
        "📺": "#e31837",
        "📊": "#f59e0b",
        "🛒": "#10b981",
        "📚": "#0277a3",
        "🌐": "#00d2ff"
    }
    return color_map.get(icon, "#00d2ff")


class NetscapeBookmarkParser(HTMLParser):
    """Robust HTML parser for Netscape bookmark format."""

    def __init__(self):
        super().__init__()
        self.bookmarks: List[Dict[str, str]] = []
        self.current_href = None
        self.current_title_parts = []
        self.in_anchor = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.in_anchor = True
            self.current_title_parts = []
            attr_dict = dict(attrs)
            href = attr_dict.get("href", "").strip()
            if href and (href.startswith("http://") or href.startswith("https://")):
                self.current_href = href
            else:
                self.current_href = None

    def handle_endtag(self, tag):
        if tag.lower() == "a":
            if self.in_anchor and self.current_href:
                title = "".join(self.current_title_parts).strip()
                if not title:
                    try:
                        parsed = urllib.parse.urlparse(self.current_href)
                        title = parsed.hostname or self.current_href
                    except Exception:
                        title = self.current_href
                self.bookmarks.append({
                    "title": title,
                    "url": self.current_href
                })
            self.in_anchor = False
            self.current_href = None
            self.current_title_parts = []

    def handle_data(self, data):
        if self.in_anchor:
            self.current_title_parts.append(data)


def build_portal_item(url: str, title: str, folder: str = "") -> Optional[Dict[str, Any]]:
    """Build a standardized portal/bookmark dictionary with icon, color and favicon."""
    url = url.strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return None

    title = title.strip()
    domain = ""
    try:
        domain = urllib.parse.urlparse(url).hostname or ""
    except Exception:
        domain = ""

    if not title:
        title = domain or url

    icon = guess_icon_for_url(url, title)
    color = guess_color_for_icon(icon)
    bg = f"linear-gradient(145deg, #091a28, {color})"
    favicon = f"https://icons.duckduckgo.com/ip3/{domain}.ico" if domain else ""

    return {
        "title": title,
        "url": url,
        "mark": icon,
        "color": color,
        "bg": bg,
        "domain": domain,
        "favicon": favicon,
        "folder": folder
    }


def parse_bookmarks_html(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse an exported bookmarks HTML file and return structured portal items.
    """
    if not os.path.exists(file_path):
        return []

    content = ""
    for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
        try:
            with open(file_path, "r", encoding=enc, errors="replace") as f:
                content = f.read()
            break
        except Exception:
            continue

    if not content:
        return []

    parser = NetscapeBookmarkParser()
    try:
        parser.feed(content)
    except Exception as e:
        print(f"[BookmarkParser] Opozorilo pri razčlenjevanju: {e}")

    results = []
    seen_urls = set()
    for item in parser.bookmarks:
        url = item["url"].strip()
        norm_key = re.sub(r"/+$", "", url).lower()
        if norm_key in seen_urls:
            continue
        seen_urls.add(norm_key)

        portal = build_portal_item(url, item.get("title", ""))
        if portal:
            results.append(portal)

    return results


def detect_browser_profiles() -> Dict[str, List[Dict[str, str]]]:
    """
    Detect all installed web browser profiles on the current Linux system.
    Returns dictionary of browser names mapped to list of available profiles.
    """
    home = os.path.expanduser("~")
    detected = {}

    # 1. Firefox
    ff_paths = glob.glob(os.path.join(home, ".mozilla/firefox/*/places.sqlite"))
    if ff_paths:
        detected["firefox"] = []
        for p in ff_paths:
            p_dir = os.path.dirname(p)
            name = os.path.basename(p_dir)
            detected["firefox"].append({"name": name, "path": p, "type": "sqlite"})

    # 2. Google Chrome
    chrome_paths = glob.glob(os.path.join(home, ".config/google-chrome/*/Bookmarks"))
    if chrome_paths:
        detected["chrome"] = []
        for p in chrome_paths:
            name = os.path.basename(os.path.dirname(p))
            detected["chrome"].append({"name": name, "path": p, "type": "json"})

    # 3. Brave Browser
    brave_paths = glob.glob(os.path.join(home, ".config/BraveSoftware/Brave-Browser/*/Bookmarks"))
    if brave_paths:
        detected["brave"] = []
        for p in brave_paths:
            name = os.path.basename(os.path.dirname(p))
            detected["brave"].append({"name": name, "path": p, "type": "json"})

    # 4. Chromium
    chromium_paths = glob.glob(os.path.join(home, ".config/chromium/*/Bookmarks"))
    if chromium_paths:
        detected["chromium"] = []
        for p in chromium_paths:
            name = os.path.basename(os.path.dirname(p))
            detected["chromium"].append({"name": name, "path": p, "type": "json"})

    # 5. Microsoft Edge for Linux
    edge_paths = glob.glob(os.path.join(home, ".config/microsoft-edge/*/Bookmarks"))
    if edge_paths:
        detected["edge"] = []
        for p in edge_paths:
            name = os.path.basename(os.path.dirname(p))
            detected["edge"].append({"name": name, "path": p, "type": "json"})

    # 6. Opera
    opera_paths = glob.glob(os.path.join(home, ".config/opera/Bookmarks"))
    if opera_paths:
        detected["opera"] = [{"name": "Default", "path": opera_paths[0], "type": "json"}]

    return detected


def import_from_firefox_profiles(profile_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Import bookmarks directly from Firefox places.sqlite.
    Uses safe copy to temporary file to avoid database lock issues.
    """
    home = os.path.expanduser("~")
    if profile_path:
        target_files = [profile_path]
    else:
        target_files = glob.glob(os.path.join(home, ".mozilla/firefox/*/places.sqlite"))

    if not target_files:
        return []

    items = []
    seen = set()

    for db_path in target_files:
        if not os.path.exists(db_path):
            continue
        try:
            with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp:
                shutil.copyfile(db_path, tmp.name)
                con = sqlite3.connect(tmp.name)
                cur = con.cursor()
                query = """
                    SELECT b.title, p.url, f.title as folder_title
                    FROM moz_bookmarks b
                    JOIN moz_places p ON b.fk = p.id
                    LEFT JOIN moz_bookmarks f ON b.parent = f.id
                    WHERE b.type = 1 AND p.url LIKE 'http%'
                    ORDER BY b.dateAdded DESC
                """
                cur.execute(query)
                for title, url, folder in cur.fetchall():
                    if not url or url.startswith("place:"):
                        continue
                    norm = re.sub(r"/+$", "", url).lower()
                    if norm in seen:
                        continue
                    seen.add(norm)
                    portal = build_portal_item(url, title or "", folder or "")
                    if portal:
                        items.append(portal)
                con.close()
        except Exception as e:
            print(f"[BookmarkImporter] Firefox import error ({db_path}): {e}")

    return items


def import_from_chromium_profiles(bookmarks_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Import bookmarks directly from Chrome / Brave / Chromium Bookmarks JSON file.
    """
    home = os.path.expanduser("~")
    if bookmarks_path:
        target_files = [bookmarks_path]
    else:
        target_files = (
            glob.glob(os.path.join(home, ".config/google-chrome/*/Bookmarks")) +
            glob.glob(os.path.join(home, ".config/BraveSoftware/Brave-Browser/*/Bookmarks")) +
            glob.glob(os.path.join(home, ".config/chromium/*/Bookmarks")) +
            glob.glob(os.path.join(home, ".config/microsoft-edge/*/Bookmarks")) +
            glob.glob(os.path.join(home, ".config/opera/Bookmarks"))
        )

    if not target_files:
        return []

    items = []
    seen = set()

    def walk_tree(node, current_folder=""):
        if isinstance(node, dict):
            node_type = node.get("type")
            if node_type == "url":
                url = node.get("url", "")
                title = node.get("name", "")
                norm = re.sub(r"/+$", "", url).lower()
                if norm not in seen:
                    seen.add(norm)
                    p = build_portal_item(url, title, current_folder)
                    if p:
                        items.append(p)
            elif node_type == "folder":
                folder_name = node.get("name") or current_folder
                for child in node.get("children", []):
                    walk_tree(child, folder_name)
            else:
                for k, v in node.items():
                    if isinstance(v, (dict, list)):
                        walk_tree(v, current_folder)
        elif isinstance(node, list):
            for el in node:
                walk_tree(el, current_folder)

    for bp in target_files:
        if not os.path.exists(bp):
            continue
        try:
            with open(bp, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
                roots = data.get("roots", {})
                for root_name, root_node in roots.items():
                    walk_tree(root_node, root_name)
        except Exception as e:
            print(f"[BookmarkImporter] Chromium import error ({bp}): {e}")

    return items


def auto_import_all_profiles() -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Scans all browser profiles on the system (Firefox, Chrome, Brave, Chromium, Edge),
    merges bookmarks without duplicates, and returns structured portal list + statistics.
    """
    stats = {}
    ff_items = import_from_firefox_profiles()
    if ff_items:
        stats["Firefox"] = len(ff_items)

    cr_items = import_from_chromium_profiles()
    if cr_items:
        stats["Chrome/Brave"] = len(cr_items)

    merged = []
    seen = set()
    for item in ff_items + cr_items:
        url = item.get("url", "")
        norm = re.sub(r"/+$", "", url).lower()
        if norm not in seen:
            seen.add(norm)
            merged.append(item)

    return merged, stats

