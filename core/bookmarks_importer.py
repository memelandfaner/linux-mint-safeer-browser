#!/usr/bin/env python3
"""
Safeer Browser - 1-Click Bookmarks & Portals Importer
Parses standard Netscape Bookmark HTML files exported from Firefox, Chrome, Chromium, Brave, Edge, Opera, etc.
"""

from html.parser import HTMLParser
import os
import re
import urllib.parse
from typing import List, Dict, Any


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
        # Normalize: strip trailing slash for deduplication check
        norm_key = re.sub(r"/+$", "", url).lower()
        if norm_key in seen_urls:
            continue
        seen_urls.add(norm_key)

        title = item["title"].strip()
        icon = guess_icon_for_url(url, title)
        color = guess_color_for_icon(icon)
        bg = f"linear-gradient(145deg, #091a28, {color})"

        results.append({
            "title": title,
            "url": url,
            "mark": icon,
            "color": color,
            "bg": bg
        })

    return results
