#!/usr/bin/env python3
"""
Safeer Browser — Linux Mint Edition
Desktop-optimized browser with Modular Sidebar (Messenger, Gmail, Custom sites),
YouTube Zero-Ad & Background Audio engine, Cyber Threat Shield, and Persistent Sessions.
"""

import os
import sys
import json
import uuid
import socket
import threading
import subprocess
import warnings
import urllib.parse
from datetime import datetime
import gi

# Suppress GTK deprecation and driver warnings for clean, smooth console output
warnings.filterwarnings("ignore")

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, Gdk, WebKit2, GLib, Gio, Pango

# Explicitly set application & program name for Linux Mint window manager & taskbar
GLib.set_prgname("safeer-browser")
GLib.set_application_name("Safeer Browser")

# Import core modules
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core.config import ConfigManager, SEARCH_ENGINES
from core.i18n import t, set_language, get_current_language, SUPPORTED_LANGUAGES
from core.adblock import (
    YOUTUBE_ADBLOCK_SCRIPT,
    GENERIC_COSMETIC_SCRIPT,
    is_threat_domain,
    FORCE_DARK_MODE_CSS
)
from core.reader import READER_MODE_JS

# Native WebKitGTK user agent matching Safari/WebKit engine to prevent Google CAPTCHA bot triggers
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
DOCK_WIDTH = 54


class SafeerMintBrowser(Gtk.Window):
    def __init__(self, initial_url=None):
        super().__init__()
        self.config = ConfigManager()

        # Initialize configured interface language
        configured_lang = self.config.get("language", "auto")
        set_language(configured_lang)
        self.set_title(f"{t('app_title')} — Linux Mint Edition")

        # Restore remembered window geometry or use 1280x820
        win_w = self.config.get("window_width", 1280)
        win_h = self.config.get("window_height", 820)
        self.set_default_size(win_w, win_h)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Set WM_CLASS so Linux Mint panel associates the window with safeer-browser.desktop
        try:
            self.set_wmclass("safeer-browser", "safeer-browser")
        except Exception:
            pass

        # Set official window & taskbar icon using system theme name and direct fallback file
        Gtk.Window.set_default_icon_name("safeer-browser")
        self.set_icon_name("safeer-browser")
        icon_path = os.path.join(BASE_DIR, "assets", "icon.png")
        if os.path.exists(icon_path):
            try:
                self.set_icon_from_file(icon_path)
                Gtk.Window.set_default_icon_from_file(icon_path)
            except Exception as e:
                print(f"[Icon] Opozorilo pri nalaganju ikone: {e}")

        self.active_sidebar_service = None
        self.dock_buttons = {}
        self.dark_style_sheet = None

        # Multi-tab state management
        self.tabs = []
        self.active_tab_id = None
        self.tab_counter = 0

        # Downloads & History state
        self.downloads = []
        self.history_file = os.path.join(self.config.config_dir, "history.json")
        self._is_fullscreen = False

        # Configure Persistent Cookie, LocalStorage & IndexedDB Storage
        self.setup_persistent_storage()
        self.setup_downloads_handling()
        self.setup_ipc_socket()

        # Apply Linux Mint Dark Theme preference
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        self.setup_ui(initial_url=initial_url)
        self.apply_css()

        # Connect F4 keyboard shortcut to toggle sidebar
        self.connect("key-press-event", self.on_global_key_press)
        # Connect delete-event to remember window size on exit
        self.connect("delete-event", self.on_delete_event)

    def on_delete_event(self, widget, event):
        """Zapomni si velikost okna in počisti IPC socket ob zaprtju."""
        try:
            w, h = self.get_size()
            if w >= 800 and h >= 600:
                self.config.set("window_width", w)
                self.config.set("window_height", h)
        except Exception:
            pass
        try:
            sock_path = os.path.join(self.config.config_dir, "safeer.sock")
            if os.path.exists(sock_path):
                os.remove(sock_path)
        except Exception:
            pass
        return False

    def setup_ipc_socket(self):
        """Lokalni Unix socket za vodenje ene same instance (odpiranje povezav iz drugih aplikacij v novih zavihkih)."""
        sock_path = os.path.join(self.config.config_dir, "safeer.sock")
        try:
            if os.path.exists(sock_path):
                try:
                    os.remove(sock_path)
                except Exception:
                    pass
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(sock_path)
            server.listen(5)
            self.ipc_server_sock = server

            def socket_listener():
                while True:
                    try:
                        conn, _ = server.accept()
                        raw_data = conn.recv(4096).decode("utf-8", errors="ignore").strip()
                        if raw_data:
                            parts = raw_data.split(" ", 1)
                            cmd = parts[0]
                            arg = parts[1] if len(parts) > 1 else ""
                            if cmd == "OPEN" and arg:
                                GLib.idle_add(self.open_url_from_external, arg)
                            elif cmd == "FOCUS":
                                GLib.idle_add(self.present)
                        conn.sendall(b"OK\n")
                        conn.close()
                    except Exception:
                        break

            t = threading.Thread(target=socket_listener, daemon=True)
            t.start()
        except Exception as e:
            print(f"[IPC Socket] Opozorilo pri inicializaciji socketa: {e}")

    def open_url_from_external(self, url):
        """Odpri povezavo iz zunanjega programa (Thunderbird, Telegram, Terminal) v novem zavihku."""
        self.present()
        if url:
            self.new_tab(url=url, switch=True)

    def setup_persistent_storage(self):
        """Omogoči trajne seje, LocalStorage in IndexedDB za Messenger, Gmail, YouTube itd."""
        try:
            data_dir = os.path.join(self.config.config_dir, "web-data")
            os.makedirs(data_dir, exist_ok=True)
            self.website_data_manager = WebKit2.WebsiteDataManager(
                base_data_directory=data_dir,
                base_cache_directory=os.path.join(data_dir, "cache"),
                disk_cache_directory=os.path.join(data_dir, "cache"),
                indexeddb_directory=os.path.join(data_dir, "indexeddb"),
                local_storage_directory=os.path.join(data_dir, "localstorage"),
                websql_directory=os.path.join(data_dir, "websql")
            )
            self.web_context = WebKit2.WebContext.new_with_website_data_manager(self.website_data_manager)
            cookie_mgr = self.website_data_manager.get_cookie_manager()
            cookie_path = os.path.join(self.config.config_dir, "cookies.sqlite")
            cookie_mgr.set_persistent_storage(cookie_path, WebKit2.CookiePersistentStorage.SQLITE)
            cookie_mgr.set_accept_policy(WebKit2.CookieAcceptPolicy.ALWAYS)
        except Exception as e:
            print(f"[Storage] Opozorilo pri nastavitvi shrambe: {e}")
            self.web_context = WebKit2.WebContext.get_default()

    def setup_ui(self, initial_url=None):
        # Main Vertical Box
        self.main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(self.main_vbox)

        # 1. Top Navigation Bar
        self.create_top_bar()
        self.main_vbox.pack_start(self.top_bar, False, False, 0)

        # 2. Main Horizontal Content Area (Sidebar + Web)
        self.content_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.main_vbox.pack_start(self.content_paned, True, True, 0)

        # Left Dock / Sidebar
        self.create_sidebar()
        self.content_paned.pack1(self.sidebar_box, False, False)

        # Right Main Web Area
        self.create_main_webview()
        self.content_paned.pack2(self.webview_container, True, False)

        # 3. Bottom Optional Virtual Keyboard (Hidden by default!)
        self.create_keyboard_panel()
        self.main_vbox.pack_end(self.keyboard_box, False, False, 0)

        # Set initial divider position (dock width only)
        self.content_paned.set_position(DOCK_WIDTH)

        # Check permanent sidebar setting
        if not self.config.get("sidebar_enabled", True):
            self.sidebar_box.hide()
            self.content_paned.set_position(0)

        # Connect paned divider moved signal to remember custom width
        self.content_paned.connect("notify::position", self.on_paned_moved)

        # Create first initial tab
        self.new_tab(url=initial_url or "safeer://home", switch=True)

    def apply_css(self):
        if not hasattr(self, 'css_provider'):
            self.css_provider = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(),
                self.css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        theme = self.config.get("theme", "midnight")
        if theme == "mint":
            bg_base = "#141c15"
            bg_card = "#1c2b1f"
            bg_tab_active = "#243b28"
            accent = "#87cf3e"
            fg_main = "#f0fdf4"
        elif theme == "neon":
            bg_base = "#090d16"
            bg_card = "#111827"
            bg_tab_active = "#1e293b"
            accent = "#00d2ff"
            fg_main = "#f0fdfa"
        elif theme == "amoled":
            bg_base = "#000000"
            bg_card = "#0e0e0e"
            bg_tab_active = "#181818"
            accent = "#38bdf8"
            fg_main = "#ffffff"
        else: # midnight
            bg_base = "#1c1b22"
            bg_card = "#2b2a33"
            bg_tab_active = "#2b2a33"
            accent = "#0060df"
            fg_main = "#fbfbfe"

        css_data = f"""
        * {{
            font-family: "Ubuntu", "Ubuntu Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        window, paned, box, .view, WebKitWebView {{
            background-color: {bg_base};
            background: {bg_base};
            color: {fg_main};
        }}

        /* 1. Firefox Proton Tab Row */
        .tab-toolbar {{
            background-color: {bg_base};
            background: {bg_base};
            padding: 5px 12px 0px 12px;
            min-height: 40px;
        }}
        .firefox-tab {{
            border-radius: 8px 8px 0 0;
            padding: 5px 12px;
            min-width: 170px;
            transition: all 120ms ease;
        }}
        .firefox-tab.active-tab {{
            background-color: {bg_tab_active};
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-bottom: none;
        }}
        .firefox-tab.inactive-tab {{
            background-color: rgba(255, 255, 255, 0.04);
            border: 1px solid transparent;
            border-bottom: none;
        }}
        .firefox-tab.inactive-tab:hover {{
            background-color: rgba(255, 255, 255, 0.08);
        }}
        .firefox-tab.inactive-tab .tab-title {{
            color: #9ca3af;
        }}
        .firefox-tab.active-tab .tab-title {{
            color: {fg_main};
        }}
        .history-tree {{
            background-color: {bg_card};
            color: {fg_main};
            font-size: 13.5px;
        }}
        .history-tree:selected {{
            background-color: {accent};
            color: #ffffff;
        }}
        .tab-icon {{
            font-size: 16px;
            color: {fg_main};
            margin-right: 4px;
        }}
        .tab-title {{
            color: {fg_main};
            font-size: 14px;
            font-weight: 600;
            margin: 0 4px;
        }}
        .tab-close-btn {{
            background: transparent;
            border: none;
            border-radius: 4px;
            color: #9ca3af;
            padding: 2px 6px;
            font-size: 13px;
        }}
        .tab-close-btn:hover {{
            background: rgba(255, 255, 255, 0.18);
            color: #ffffff;
        }}
        .new-tab-btn {{
            background: transparent;
            border: none;
            border-radius: 6px;
            color: #cfcfd8;
            padding: 2px 10px;
            font-size: 20px;
            font-weight: 500;
            margin-left: 6px;
        }}
        .new-tab-btn:hover {{
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
        }}

        /* 2. Firefox Proton Nav Toolbar */
        .nav-toolbar {{
            background-color: {bg_base};
            background: {bg_base};
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding: 4px 10px 6px 10px;
        }}
        .ff-nav-btn {{
            background: transparent;
            border: none;
            border-radius: 6px;
            color: #e0e0e6;
            padding: 6px 10px;
            font-size: 16px;
            font-weight: 600;
            margin-right: 2px;
            transition: all 100ms ease;
        }}
        .ff-nav-btn:hover {{
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
        }}
        .ff-nav-btn.active {{
            background: {accent};
            color: #ffffff;
        }}

        /* 3. Firefox Awesomebar / URL Entry */
        .ff-url-container {{
            background-color: {bg_card};
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            padding: 2px 12px;
            min-height: 42px;
        }}
        .ff-url-container:focus-within {{
            border-color: {accent};
            box-shadow: 0 0 0 2px rgba(0, 96, 223, 0.4);
        }}
        .ff-shield-btn {{
            background: transparent;
            border: none;
            padding: 2px 6px;
            font-size: 16px;
        }}
        .ff-security-icon {{
            font-size: 15px;
            color: #38bdf8;
            margin-right: 4px;
        }}
        .ff-url-entry {{
            background: transparent;
            background-color: transparent;
            border: none;
            box-shadow: none;
            color: #ffffff;
            font-size: 16.5px;
            font-weight: 600;
            padding: 6px 8px;
        }}
        .ff-action-btn {{
            background: transparent;
            border: none;
            border-radius: 6px;
            color: #9ca3af;
            padding: 3px 6px;
            font-size: 15px;
            margin-left: 2px;
            transition: all 120ms ease;
        }}
        .ff-action-btn:hover {{
            background: rgba(255, 255, 255, 0.12);
            color: #ffffff;
        }}
        .ff-action-btn.active-star {{
            color: #eab308;
            font-size: 16px;
        }}
        .ff-action-btn.reader-active {{
            color: #38bdf8;
            background: rgba(56, 189, 248, 0.2);
        }}
        .tab-audio-btn {{
            background: transparent;
            border: none;
            border-radius: 4px;
            padding: 2px 4px;
            font-size: 12px;
            color: #38bdf8;
            transition: all 100ms ease;
        }}
        .tab-audio-btn:hover {{
            background: rgba(255, 255, 255, 0.15);
            color: #ffffff;
        }}

        /* 4. Left Dock and Sidebar */
        .dock-bar {{
            background-color: {bg_base};
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            padding: 8px 4px;
        }}
        .dock-btn {{
            background: transparent;
            border: none;
            border-radius: 8px;
            padding: 8px 6px;
            font-size: 18px;
            color: #9ca3af;
            margin-bottom: 4px;
            transition: all 120ms ease;
        }}
        .dock-btn:hover {{
            background: rgba(255, 255, 255, 0.08);
            color: #ffffff;
        }}
        .dock-btn.active {{
            background: rgba(0, 221, 255, 0.15);
            border-left: 3px solid {accent};
            color: {accent};
        }}
        .drawer-box {{
            background-color: {bg_base};
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .drawer-header-bar {{
            background: {bg_card};
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding: 8px 14px;
            min-height: 44px;
        }}
        .btn-delete {{
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #ef4444;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
        }}
        .btn-delete:hover {{
            background: #ef4444;
            color: #ffffff;
        }}
        .code-editor {{
            font-family: "JetBrains Mono", "Courier New", monospace;
            background-color: #11141d;
            color: #38bdf8;
            font-size: 13px;
        }}

        /* 5. Customizer Studio Dialog & Modern Component Styling */
        .customizer-dialog {{
            background-color: {bg_base};
            color: {fg_main};
        }}
        .customizer-banner {{
            background: linear-gradient(135deg, rgba(0, 96, 223, 0.22) 0%, rgba(135, 207, 62, 0.16) 100%);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 12px;
            padding: 12px 18px;
            margin-bottom: 6px;
        }}
        .banner-icon {{
            font-size: 26px;
        }}
        .customizer-notebook {{
            background-color: transparent;
            border: none;
        }}
        .customizer-notebook tab {{
            background-color: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px 8px 0 0;
            padding: 8px 16px;
            color: #94a3b8;
            font-size: 13.5px;
            font-weight: 600;
            margin-right: 6px;
            transition: all 120ms ease;
        }}
        .customizer-notebook tab:hover {{
            background-color: rgba(255, 255, 255, 0.07);
            color: #ffffff;
        }}
        .customizer-notebook tab:checked {{
            background-color: {bg_card};
            border-color: rgba(255, 255, 255, 0.14);
            border-bottom: 2px solid {accent};
            color: #ffffff;
        }}
        .theme-card-box {{
            background-color: {bg_card};
            border: 1.5px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 14px 16px;
            transition: all 120ms ease;
        }}
        .theme-card-box:hover {{
            border-color: rgba(255, 255, 255, 0.24);
            background-color: rgba(255, 255, 255, 0.06);
        }}
        .theme-card-box.active-theme {{
            border: 2px solid {accent};
            background-color: rgba(0, 96, 223, 0.09);
        }}
        .theme-badge {{
            background: rgba(255, 255, 255, 0.08);
            color: #94a3b8;
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 600;
        }}
        .theme-badge.active-badge {{
            background: {accent};
            color: #ffffff;
        }}
        .snippet-chip {{
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            color: #e2e8f0;
            padding: 6px 12px;
            font-size: 12.5px;
            font-weight: 600;
            transition: all 100ms ease;
        }}
        .snippet-chip:hover {{
            background-color: rgba(0, 210, 255, 0.15);
            border-color: #00d2ff;
            color: #00d2ff;
        }}
        .item-card-row {{
            background-color: {bg_card};
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            padding: 10px 14px;
            transition: all 100ms ease;
        }}
        .item-card-row:hover {{
            border-color: rgba(255, 255, 255, 0.18);
            background-color: rgba(255, 255, 255, 0.05);
        }}
        .btn-primary-glow {{
            background: linear-gradient(135deg, {accent}, #0284c7);
            border: none;
            border-radius: 8px;
            color: #ffffff;
            font-weight: 700;
            padding: 8px 18px;
        }}
        .btn-primary-glow:hover {{
            opacity: 0.9;
        }}
        .customizer-close-btn {{
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            color: #f1f5f9;
            font-weight: 600;
            padding: 7px 22px;
        }}
        .customizer-close-btn:hover {{
            background: rgba(255, 255, 255, 0.16);
            color: #ffffff;
        }}
        """

        custom_css = self.config.get("custom_css", "")
        if custom_css:
            css_data += "\n/* Uporabniški lasten CSS */\n" + custom_css

        self.css_provider.load_from_data(css_data.encode("utf-8"))

    def on_global_key_press(self, widget, event):
        ctrl = (event.state & Gdk.ModifierType.CONTROL_MASK) != 0
        alt = (event.state & Gdk.ModifierType.MOD1_MASK) != 0
        shift = (event.state & Gdk.ModifierType.SHIFT_MASK) != 0

        # Ctrl + Shift + Delete opens Clear Browsing Data dialog (Universal standard)
        if ctrl and shift and event.keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete):
            self.open_clear_data_dialog()
            return True

        # F11 toggles Fullscreen
        if event.keyval == Gdk.KEY_F11:
            self.toggle_fullscreen()
            return True

        # Ctrl + L or F6 focuses URL bar & selects text (Universal browser standard)
        if (ctrl and event.keyval in (Gdk.KEY_l, Gdk.KEY_L)) or event.keyval == Gdk.KEY_F6:
            self.url_entry.grab_focus()
            self.url_entry.select_region(0, -1)
            return True

        # Escape while URL bar has focus restores URL and returns focus to webview
        if event.keyval == Gdk.KEY_Escape and self.url_entry.has_focus():
            wv = self.get_active_webview()
            cur_uri = wv.get_uri() if wv else ""
            self.url_entry.set_text(self.format_clean_url(cur_uri))
            if wv:
                wv.grab_focus()
            return True

        # Zoom in: Ctrl + Plus / Ctrl + = / Ctrl + KP_Add
        if ctrl and event.keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self.zoom_in()
            return True

        # Zoom out: Ctrl + Minus / Ctrl + KP_Subtract
        if ctrl and event.keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            self.zoom_out()
            return True

        # Reset zoom: Ctrl + 0 / Ctrl + KP_0
        if ctrl and event.keyval in (Gdk.KEY_0, Gdk.KEY_KP_0):
            self.zoom_reset()
            return True

        # F4 toggles sidebar
        if event.keyval == Gdk.KEY_F4:
            self.toggle_sidebar_visibility()
            return True

        # Ctrl + T: New tab
        elif ctrl and event.keyval in (Gdk.KEY_t, Gdk.KEY_T):
            self.new_tab()
            return True

        # Ctrl + W: Close tab
        elif ctrl and event.keyval in (Gdk.KEY_w, Gdk.KEY_W):
            if self.active_tab_id:
                self.close_tab(self.active_tab_id)
            return True

        # Ctrl + H: History
        elif ctrl and event.keyval in (Gdk.KEY_h, Gdk.KEY_H):
            self.open_history_dialog()
            return True

        # Ctrl + J: Downloads
        elif ctrl and event.keyval in (Gdk.KEY_j, Gdk.KEY_J):
            self.open_downloads_dialog()
            return True

        # Ctrl + Shift + D: Toggle Dark Mode
        elif ctrl and shift and event.keyval in (Gdk.KEY_d, Gdk.KEY_D):
            self.toggle_dark_mode()
            return True

        # Ctrl + Alt + R or Alt + R: Reader Mode (Distraction-Free)
        elif (ctrl and alt and event.keyval in (Gdk.KEY_r, Gdk.KEY_R)) or (alt and event.keyval in (Gdk.KEY_r, Gdk.KEY_R)):
            self.toggle_reader_mode()
            return True

        # Ctrl + M: Toggle Mute Audio on Active Tab
        elif ctrl and not alt and not shift and event.keyval in (Gdk.KEY_m, Gdk.KEY_M):
            self.toggle_active_tab_mute()
            return True

        # Ctrl + D: Bookmark current page to Portals / Favorites
        elif ctrl and not shift and event.keyval in (Gdk.KEY_d, Gdk.KEY_D):
            self.bookmark_current_page()
            return True

        # Ctrl + B: Open Portals / Bookmarks dialog
        elif ctrl and event.keyval in (Gdk.KEY_b, Gdk.KEY_B):
            self.open_portals_dialog()
            return True

        # Ctrl + R or F5: Reload
        elif (ctrl and event.keyval in (Gdk.KEY_r, Gdk.KEY_R)) or event.keyval == Gdk.KEY_F5:
            wv = self.get_active_webview()
            if wv:
                wv.reload()
            return True

        # Alt + Left: Back
        elif alt and event.keyval == Gdk.KEY_Left:
            wv = self.get_active_webview()
            if wv:
                wv.go_back()
            return True

        # Alt + Right: Forward
        elif alt and event.keyval == Gdk.KEY_Right:
            wv = self.get_active_webview()
            if wv:
                wv.go_forward()
            return True
        return False

    def zoom_in(self):
        wv = self.get_active_webview()
        if wv:
            cur = wv.get_zoom_level()
            wv.set_zoom_level(min(cur + 0.1, 3.0))

    def zoom_out(self):
        wv = self.get_active_webview()
        if wv:
            cur = wv.get_zoom_level()
            wv.set_zoom_level(max(cur - 0.1, 0.4))

    def zoom_reset(self):
        wv = self.get_active_webview()
        if wv:
            wv.set_zoom_level(1.0)

    def toggle_fullscreen(self):
        if getattr(self, "_is_fullscreen", False):
            self.unfullscreen()
            self._is_fullscreen = False
        else:
            self.fullscreen()
            self._is_fullscreen = True

    def bookmark_current_page(self):
        self.toggle_bookmark_current_page()

    def toggle_bookmark_current_page(self, btn=None):
        """Doda trenutno stran med priljubljene portale (Speed Dial) ali odpre urejanje."""
        wv = self.get_active_webview()
        if not wv:
            return
        uri = wv.get_uri() or ""
        title = wv.get_title() or "Priljubljena stran"
        if not uri or "home.html" in uri or uri == "safeer://home":
            return
        portals = self.config.get_portals()
        norm_uri = uri.rstrip("/")
        existing = next((p for p in portals if p.get("url", "").rstrip("/") == norm_uri), None)
        if existing:
            self.open_portal_editor_dialog(existing, on_saved=self.update_star_status)
        else:
            self.open_portal_editor_dialog(None, prefill={"title": title, "url": uri}, on_saved=self.update_star_status)

    def toggle_reader_mode(self, btn=None):
        """Preklopi aktivno stran v bralni način (Reader Mode) ali nazaj."""
        wv = self.get_active_webview()
        if not wv:
            return
        uri = wv.get_uri() or ""
        if not uri or uri.startswith("safeer://") or "home.html" in uri:
            return
        wv.run_javascript(READER_MODE_JS, None, None, None)

    def toggle_pip(self, btn=None):
        """Preklopi video v sliko v sliki (Picture-in-Picture)."""
        wv = self.get_active_webview()
        if not wv:
            return
        js = """
        (function() {
            const v = document.querySelector('video');
            if (v) {
                if (document.pictureInPictureElement) {
                    document.exitPictureInPicture().catch(console.error);
                } else if (v.requestPictureInPicture) {
                    v.requestPictureInPicture().catch(console.error);
                }
            }
        })();
        """
        wv.run_javascript(js, None, None, None)

    def toggle_active_tab_mute(self):
        """Utiša ali odtiša zvok v aktivnem zavihku."""
        wv = self.get_active_webview()
        if wv:
            muted = not wv.get_property("is-muted")
            wv.set_is_muted(muted)

    def update_star_status(self):
        """Posodobi videz zvezdice in orodij v naslovni vrstici."""
        if not hasattr(self, 'btn_star'):
            return
        wv = self.get_active_webview()
        if not wv:
            return
        uri = wv.get_uri() or ""
        if not uri or uri.startswith("safeer://") or "home.html" in uri:
            self.btn_star.hide()
            if hasattr(self, 'btn_reader'): self.btn_reader.hide()
            if hasattr(self, 'btn_pip'): self.btn_pip.hide()
            return

        self.btn_star.show()
        if hasattr(self, 'btn_reader'): self.btn_reader.show()
        if hasattr(self, 'btn_pip'): self.btn_pip.show()

        portals = self.config.get_portals()
        norm_uri = uri.rstrip("/")
        is_saved = any(p.get("url", "").rstrip("/") == norm_uri for p in portals)
        ctx = self.btn_star.get_style_context()
        if is_saved:
            self.btn_star.set_label("⭐")
            ctx.add_class("active-star")
            self.btn_star.set_tooltip_text(f"{t('page_bookmarked')}")
        else:
            self.btn_star.set_label("☆")
            ctx.remove_class("active-star")
            self.btn_star.set_tooltip_text(f"{t('bookmark_page')} (Ctrl + D)")

    def create_top_bar(self):
        # Master header container (Tabs + Navigation bar in Firefox Proton layout)
        self.top_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # 1. Tier 1: Firefox Tab Strip
        self.tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.tab_bar.get_style_context().add_class("tab-toolbar")

        # Dynamic tabs container
        self.tabs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.tab_bar.pack_start(self.tabs_box, False, False, 0)

        # New Tab Button (+)
        self.btn_new_tab = Gtk.Button(label="+")
        self.btn_new_tab.get_style_context().add_class("new-tab-btn")
        self.btn_new_tab.set_tooltip_text(f"{t('new_tab')} (Ctrl + T)")
        self.btn_new_tab.connect("clicked", lambda b: self.new_tab())
        self.tab_bar.pack_start(self.btn_new_tab, False, False, 0)

        self.top_bar.pack_start(self.tab_bar, False, False, 0)

        # 2. Tier 2: Firefox Navigation Bar
        self.nav_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.nav_bar.get_style_context().add_class("nav-toolbar")

        # Sidebar button (▤)
        self.btn_sidebar = Gtk.Button(label="▤")
        self.btn_sidebar.get_style_context().add_class("ff-nav-btn")
        self.btn_sidebar.set_tooltip_text(f"{t('sidebar_display')} (F4)")
        self.btn_sidebar.connect("clicked", lambda b: self.toggle_sidebar_visibility())
        self.nav_bar.pack_start(self.btn_sidebar, False, False, 0)

        # Back (←)
        self.btn_back = Gtk.Button(label="←")
        self.btn_back.get_style_context().add_class("ff-nav-btn")
        self.btn_back.set_tooltip_text(f"{t('back')} (Alt + ←)")
        self.btn_back.connect("clicked", lambda b: self.get_active_webview() and self.get_active_webview().go_back())
        self.nav_bar.pack_start(self.btn_back, False, False, 0)

        # Forward (→)
        self.btn_forward = Gtk.Button(label="→")
        self.btn_forward.get_style_context().add_class("ff-nav-btn")
        self.btn_forward.set_tooltip_text(f"{t('forward')} (Alt + →)")
        self.btn_forward.connect("clicked", lambda b: self.get_active_webview() and self.get_active_webview().go_forward())
        self.nav_bar.pack_start(self.btn_forward, False, False, 0)

        # Reload (↻)
        self.btn_reload = Gtk.Button(label="↻")
        self.btn_reload.get_style_context().add_class("ff-nav-btn")
        self.btn_reload.set_tooltip_text(f"{t('reload')} (F5 / Ctrl + R)")
        self.btn_reload.connect("clicked", lambda b: self.get_active_webview() and self.get_active_webview().reload())
        self.nav_bar.pack_start(self.btn_reload, False, False, 0)

        # 3. Firefox Awesomebar / URL Box
        self.url_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.url_box.get_style_context().add_class("ff-url-container")

        # Tracking protection shield inside URL bar
        self.btn_shield = Gtk.Button(label="🛡️")
        self.btn_shield.get_style_context().add_class("ff-shield-btn")
        self.btn_shield.set_tooltip_text(f"{t('app_title')} Cyber Shield: {t('adblock_active')}")
        self.btn_shield.connect("clicked", lambda b: self.show_shield_status_dialog())
        self.url_box.pack_start(self.btn_shield, False, False, 0)

        # Security tune sliders icon
        self.security_icon = Gtk.Label(label="🎚️")
        self.security_icon.get_style_context().add_class("ff-security-icon")
        self.url_box.pack_start(self.security_icon, False, False, 0)

        # Clean URL Entry with large Ubuntu font
        self.url_entry = Gtk.Entry()
        self.url_entry.get_style_context().add_class("ff-url-entry")
        self.url_entry.set_placeholder_text(t('search_placeholder'))
        self.url_entry.connect("activate", self.on_url_activate)
        self.url_entry.connect("focus-in-event", self.on_url_focus_in)
        self.url_entry.connect("focus-out-event", self.on_url_focus_out)
        self.url_box.pack_start(self.url_entry, True, True, 0)

        # Reader Mode Button (📖)
        self.btn_reader = Gtk.Button(label="📖")
        self.btn_reader.get_style_context().add_class("ff-action-btn")
        self.btn_reader.set_tooltip_text(t('reader_mode'))
        self.btn_reader.connect("clicked", lambda b: self.toggle_reader_mode())
        self.url_box.pack_start(self.btn_reader, False, False, 0)

        # Picture-in-Picture Button (⧉)
        self.btn_pip = Gtk.Button(label="⧉")
        self.btn_pip.get_style_context().add_class("ff-action-btn")
        self.btn_pip.set_tooltip_text(f"{t('pip_video')}")
        self.btn_pip.connect("clicked", lambda b: self.toggle_pip())
        self.url_box.pack_start(self.btn_pip, False, False, 0)

        # Speed Dial / Bookmark Star Button (⭐ / ☆)
        self.btn_star = Gtk.Button(label="☆")
        self.btn_star.get_style_context().add_class("ff-action-btn")
        self.btn_star.set_tooltip_text(f"{t('bookmark_page')} (Ctrl + D)")
        self.btn_star.connect("clicked", self.toggle_bookmark_current_page)
        self.url_box.pack_start(self.btn_star, False, False, 0)

        self.nav_bar.pack_start(self.url_box, True, True, 4)

        # Force Dark Mode Toggle Button (🌙 / ☀️)
        is_dark = self.config.get("force_dark_mode", False)
        self.btn_dark_mode = Gtk.Button(label="🌙" if is_dark else "☀️")
        self.btn_dark_mode.get_style_context().add_class("ff-nav-btn")
        if is_dark:
            self.btn_dark_mode.get_style_context().add_class("active")
        self.btn_dark_mode.set_tooltip_text(f"{t('force_dark_mode')}")
        self.btn_dark_mode.connect("clicked", self.toggle_dark_mode)
        self.nav_bar.pack_start(self.btn_dark_mode, False, False, 0)

        # Downloads Button (📥)
        self.btn_downloads = Gtk.Button(label="📥")
        self.btn_downloads.get_style_context().add_class("ff-nav-btn")
        self.btn_downloads.set_tooltip_text(f"{t('downloads')} (Ctrl + J)")
        self.btn_downloads.connect("clicked", lambda b: self.open_downloads_dialog())
        self.nav_bar.pack_start(self.btn_downloads, False, False, 0)

        # History Button (🕒)
        self.btn_history = Gtk.Button(label="🕒")
        self.btn_history.get_style_context().add_class("ff-nav-btn")
        self.btn_history.set_tooltip_text(f"{t('history')} (Ctrl + H)")
        self.btn_history.connect("clicked", lambda b: self.open_history_dialog())
        self.nav_bar.pack_start(self.btn_history, False, False, 0)

        # Customizer & Scripts Button (🧩)
        self.btn_customizer = Gtk.Button(label="🧩")
        self.btn_customizer.get_style_context().add_class("ff-nav-btn")
        self.btn_customizer.set_tooltip_text(f"{t('customizer_title')}")
        self.btn_customizer.connect("clicked", lambda b: self.open_customizer_dialog())
        self.nav_bar.pack_start(self.btn_customizer, False, False, 0)

        # Virtual Keyboard Button (⌨️)
        self.btn_keyboard = Gtk.Button(label="⌨️")
        self.btn_keyboard.get_style_context().add_class("ff-nav-btn")
        self.btn_keyboard.set_tooltip_text("Navidezna tipkovnica")
        self.btn_keyboard.connect("clicked", self.toggle_virtual_keyboard)
        self.nav_bar.pack_start(self.btn_keyboard, False, False, 0)

        self.top_bar.pack_start(self.nav_bar, False, False, 0)

    def show_shield_status_dialog(self):
        """Prikaže podrobno varnostno poročilo ščita."""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="🛡️ Safeer Cyber Shield — Linux Mint Aktivna Zaščita"
        )
        msg = (
            "✓ YouTube Adblock: Zero-ad hitro preskakovanje oglasov aktivno.\n"
            "✓ YouTube Background Audio: Predvajanje se nemoteno nadaljuje ob menjavi zavihkov.\n"
            "✓ Ambient Mode: Odstranjena zamegljenost in neželeni sivi okvirji.\n"
            "✓ abuse.ch Botnet Shield: Aktivno blokiranje C2 strežnikov in phishing domen.\n"
            "✓ Čista prijava: Zaščita ne posega v obrazce za prijavo (Facebook, Google, Messenger)."
        )
        dialog.format_secondary_text(msg)
        dialog.run()
        dialog.destroy()

    def toggle_sidebar_visibility(self):
        """Začasno skrije ali prikaže celotno stransko orodno vrstico."""
        if self.sidebar_box.is_visible():
            self.sidebar_box.hide()
            self.content_paned.set_position(0)
            self.btn_sidebar.get_style_context().remove_class("active")
        else:
            self.sidebar_box.show()
            self.icon_dock.show_all()
            if self.active_sidebar_service:
                self.sidebar_drawer.show()
                for c in self.sidebar_drawer.get_children():
                    c.show_all()
                drawer_w = self.config.get("sidebar_width", 420)
                if drawer_w > 650 or drawer_w < 300:
                    drawer_w = 420
                target_w = DOCK_WIDTH + drawer_w
                self.content_paned.set_position(target_w)
            else:
                self.sidebar_drawer.hide()
                self.content_paned.set_position(DOCK_WIDTH)
            self.btn_sidebar.get_style_context().add_class("active")

    def create_sidebar(self):
        # Outer sidebar box: icon dock strip + slide-out webview drawer
        self.sidebar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        # 1. Left Icon Dock
        self.icon_dock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.icon_dock.get_style_context().add_class("dock-bar")
        self.sidebar_box.pack_start(self.icon_dock, False, False, 0)

        # 2. Slide-out Panel (Drawer)
        self.sidebar_drawer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.sidebar_drawer.get_style_context().add_class("drawer-box")
        self.sidebar_drawer.set_size_request(380, -1)
        self.sidebar_drawer.set_no_show_all(True)
        self.sidebar_drawer.hide()

        # Drawer Header
        self.drawer_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.drawer_header.get_style_context().add_class("drawer-header-bar")
        
        self.drawer_title = Gtk.Label(label="Stranska integracija")
        self.drawer_title.set_halign(Gtk.Align.START)
        self.drawer_header.pack_start(self.drawer_title, True, True, 6)

        # Back button in drawer
        btn_back_drawer = Gtk.Button(label="◀")
        btn_back_drawer.set_tooltip_text("Nazaj v stranski integraciji")
        btn_back_drawer.get_style_context().add_class("nav-btn")
        btn_back_drawer.connect("clicked", lambda b: self.sidebar_webview.go_back())
        self.drawer_header.pack_start(btn_back_drawer, False, False, 0)

        # Reload button in drawer
        btn_reload_drawer = Gtk.Button(label="⟳")
        btn_reload_drawer.set_tooltip_text("Osveži stransko integracijo")
        btn_reload_drawer.get_style_context().add_class("nav-btn")
        btn_reload_drawer.connect("clicked", lambda b: self.sidebar_webview.reload())
        self.drawer_header.pack_start(btn_reload_drawer, False, False, 0)

        # Open in Main Tab button (↗️)
        btn_popout = Gtk.Button(label="↗️")
        btn_popout.set_tooltip_text("Odpri to stran v glavnem oknu brskalnika")
        btn_popout.get_style_context().add_class("nav-btn")
        btn_popout.connect("clicked", self.popout_sidebar_to_main)
        self.drawer_header.pack_start(btn_popout, False, False, 0)

        # Expand / Shrink drawer width toggle (↔️)
        self.btn_expand_drawer = Gtk.Button(label="↔️")
        self.btn_expand_drawer.set_tooltip_text("Razširi predal (720px) za sočasen celovit pogled klepeta ali skrči (420px)")
        self.btn_expand_drawer.get_style_context().add_class("nav-btn")
        self.btn_expand_drawer.connect("clicked", self.toggle_drawer_width)
        self.drawer_header.pack_start(self.btn_expand_drawer, False, False, 0)

        # Close button in drawer
        btn_close_drawer = Gtk.Button(label="✕")
        btn_close_drawer.set_tooltip_text("Zapri stranski zavihek")
        btn_close_drawer.get_style_context().add_class("nav-btn")
        btn_close_drawer.connect("clicked", lambda b: self.close_sidebar_panel())
        self.drawer_header.pack_start(btn_close_drawer, False, False, 0)

        self.sidebar_drawer.pack_start(self.drawer_header, False, False, 0)

        # Drawer WebView: uses shared persistent web_context
        self.sidebar_webview = WebKit2.WebView.new_with_context(self.web_context)
        self.setup_webview_settings(self.sidebar_webview)
        self.sidebar_webview.connect("create", self.on_create_webview)
        self.sidebar_webview.connect("decide-policy", self.on_decide_policy)

        self.sidebar_drawer.pack_start(self.sidebar_webview, True, True, 0)

        self.sidebar_box.pack_start(self.sidebar_drawer, True, True, 0)

        # Populate icon dock with current integrations
        self.rebuild_icon_dock()

    def rebuild_icon_dock(self):
        """Dinamično ponovno zgradi ikone v stranski orodni vrstici."""
        for child in self.icon_dock.get_children():
            self.icon_dock.remove(child)

        self.dock_buttons = {}
        integrations = self.config.get("integrations", {})
        for s_id, s_data in integrations.items():
            if s_data.get("enabled", True):
                btn = Gtk.Button(label=s_data.get("icon", "🌐"))
                btn.set_tooltip_text(f"{s_data.get('name', 'Stran')}\n{s_data.get('url', '')}")
                btn.get_style_context().add_class("dock-btn")
                if self.active_sidebar_service == s_id:
                    btn.get_style_context().add_class("active")
                btn.connect("clicked", lambda b, sid=s_id: self.toggle_sidebar_panel(sid))
                self.icon_dock.pack_start(btn, False, False, 0)
                self.dock_buttons[s_id] = btn

        # Spacer to push action buttons to bottom
        spacer = Gtk.Box()
        self.icon_dock.pack_start(spacer, True, True, 0)

        # Quick Add Page button (+)
        btn_add = Gtk.Button(label="➕")
        btn_add.set_tooltip_text("Dodaj poljubno spletno stran v stransko vrstico")
        btn_add.get_style_context().add_class("dock-btn")
        btn_add.connect("clicked", lambda b: self.open_add_page_dialog())
        self.icon_dock.pack_start(btn_add, False, False, 0)

        # Settings Button (⚙️)
        btn_settings = Gtk.Button(label="⚙️")
        btn_settings.set_tooltip_text("Nastavitve in urejanje stranske vrstice")
        btn_settings.get_style_context().add_class("dock-btn")
        btn_settings.connect("clicked", lambda b: self.open_settings_dialog())
        self.icon_dock.pack_start(btn_settings, False, False, 0)

        self.icon_dock.show_all()

    def popout_sidebar_to_main(self, widget=None):
        uri = self.sidebar_webview.get_uri()
        if uri:
            wv = self.get_active_webview()
            if wv:
                wv.load_uri(uri)
            self.close_sidebar_panel()

    def toggle_drawer_width(self, widget=None):
        """Preklopi med polno (680px) in kompaktno (420px) širino predala."""
        current_w = self.config.get("sidebar_width", 680)
        if current_w >= 600:
            new_w = 420
            self.btn_expand_drawer.set_label("↔️")
        else:
            new_w = 680
            self.btn_expand_drawer.set_label("◀▶")
        self.config.set("sidebar_width", new_w)
        self.content_paned.set_position(DOCK_WIDTH + new_w)

    def toggle_sidebar_panel(self, service_id: str):
        # If clicking the currently open service, toggle it closed
        if self.active_sidebar_service == service_id and self.sidebar_drawer.is_visible():
            self.close_sidebar_panel()
            return

        integrations = self.config.get("integrations", {})
        if service_id in integrations:
            service = integrations[service_id]
            self.drawer_title.set_text(f"{service.get('icon', '')} {service.get('name', '')}")
            
            # Load URL if different or not loaded
            cur_uri = self.sidebar_webview.get_uri() or ""
            target_url = service.get("url", "")
            if target_url and (cur_uri != target_url and not cur_uri.startswith(target_url)):
                self.sidebar_webview.load_uri(target_url)

            # Show drawer and expand divider to comfortable desktop width
            self.sidebar_drawer.show()
            for c in self.sidebar_drawer.get_children():
                c.show_all()
            drawer_w = self.config.get("sidebar_width", 680)
            if drawer_w < 550:
                drawer_w = 680
            target_width = DOCK_WIDTH + drawer_w
            self.content_paned.set_position(target_width)
            self.active_sidebar_service = service_id

            # Update active dock button styling
            for sid, btn in self.dock_buttons.items():
                if sid == service_id:
                    btn.get_style_context().add_class("active")
                else:
                    btn.get_style_context().remove_class("active")

    def close_sidebar_panel(self):
        self.sidebar_drawer.hide()
        self.active_sidebar_service = None
        self.content_paned.set_position(DOCK_WIDTH)
        for btn in self.dock_buttons.values():
            btn.get_style_context().remove_class("active")

    def on_paned_moved(self, paned, param):
        pos = paned.get_position()
        if self.sidebar_drawer.is_visible() and pos > DOCK_WIDTH + 100:
            drawer_w = pos - DOCK_WIDTH
            if 350 <= drawer_w <= 950:
                self.config.set("sidebar_width", drawer_w)

    def on_create_webview(self, webview, navigation_action):
        """Obravnava klice window.open ali povezave target=_blank."""
        try:
            req = navigation_action.get_request()
            uri = req.get_uri() if req else ""
            if uri:
                if webview == self.sidebar_webview:
                    self.sidebar_webview.load_uri(uri)
                else:
                    self.new_tab(url=uri, switch=True)
        except Exception as e:
            print(f"[Create WebView] Napaka: {e}")
        return None

    def on_decide_policy(self, webview, decision, decision_type):
        """Obravnava zahteve za nova okna (target=_blank) in navigacijo."""
        if decision_type == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
            try:
                nav_action = decision.get_navigation_action()
                req = nav_action.get_request()
                uri = req.get_uri() if req else ""
                if uri:
                    if webview == self.sidebar_webview:
                        self.sidebar_webview.load_uri(uri)
                    else:
                        self.new_tab(url=uri, switch=True)
                decision.ignore()
                return True
            except Exception as e:
                print(f"[Policy] Napaka pri novem oknu: {e}")
        elif decision_type == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            try:
                nav_action = decision.get_navigation_action()
                mouse_btn = nav_action.get_mouse_button()
                modifiers = nav_action.get_modifiers()
                # Srednji klik (kolešček) ali Ctrl + klik odpre povezavo v novem zavihku v ozadju!
                if mouse_btn == 2 or (modifiers & Gdk.ModifierType.CONTROL_MASK):
                    req = nav_action.get_request()
                    uri = req.get_uri() if req else ""
                    if uri:
                        self.new_tab(url=uri, switch=False)
                    decision.ignore()
                    return True
            except Exception:
                pass
            decision.use()
            return True
        return False

    def open_add_page_dialog(self):
        """Dialog za hitro dodajanje nove strani v stransko orodno vrstico."""
        dialog = Gtk.Dialog(
            title=f"➕ {t('add_portal', 'Dodaj stran')} — Safeer",
            transient_for=self,
            flags=0
        )
        dialog.get_style_context().add_class("customizer-dialog")
        btn_cancel = dialog.add_button(t("cancel", "Prekliči"), Gtk.ResponseType.CANCEL)
        btn_cancel.get_style_context().add_class("customizer-close-btn")
        btn_add = dialog.add_button(f"➕ {t('add_portal', 'Dodaj')}", Gtk.ResponseType.OK)
        btn_add.get_style_context().add_class("btn-primary-glow")
        dialog.set_default_size(420, 260)

        box = dialog.get_content_area()
        box.set_spacing(10)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        lbl_name = Gtk.Label(label="Ime spletne strani (npr. Discord, WhatsApp, ChatGPT):")
        lbl_name.set_halign(Gtk.Align.START)
        entry_name = Gtk.Entry()
        entry_name.set_placeholder_text("Vnesite ime...")
        box.pack_start(lbl_name, False, False, 0)
        box.pack_start(entry_name, False, False, 0)

        lbl_url = Gtk.Label(label="Spletni naslov (URL):")
        lbl_url.set_halign(Gtk.Align.START)
        entry_url = Gtk.Entry()
        entry_url.set_placeholder_text("https://...")
        box.pack_start(lbl_url, False, False, 0)
        box.pack_start(entry_url, False, False, 0)

        lbl_icon = Gtk.Label(label="Ikona ali emoji (npr. 💬, 🤖, 🎧, ✉️, 🌐):")
        lbl_icon.set_halign(Gtk.Align.START)
        entry_icon = Gtk.Entry()
        entry_icon.set_text("🌐")
        box.pack_start(lbl_icon, False, False, 0)
        box.pack_start(entry_icon, False, False, 0)

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            name = entry_name.get_text().strip()
            url = entry_url.get_text().strip()
            icon = entry_icon.get_text().strip() or "🌐"

            if name and url:
                new_id = self.config.add_integration(name, url, icon)
                self.rebuild_icon_dock()
                self.toggle_sidebar_panel(new_id)

        dialog.destroy()

    def open_settings_dialog(self):
        """Celovit dialog za nastavitve stranske vrstice in brskalnika."""
        dialog = Gtk.Dialog(
            title=f"⚙️ {t('settings')} — Safeer",
            transient_for=self,
            flags=0
        )
        dialog.set_default_size(540, 580)
        dialog.get_style_context().add_class("customizer-dialog")
        btn_close = dialog.add_button(t("close", "Zapri"), Gtk.ResponseType.CLOSE)
        btn_close.get_style_context().add_class("customizer-close-btn")

        box = dialog.get_content_area()
        box.set_spacing(12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # 0. Global Language Selection
        title_lang = Gtk.Label(label=f"<b>🌐 {t('language')}:</b>")
        title_lang.set_use_markup(True)
        title_lang.set_halign(Gtk.Align.START)
        box.pack_start(title_lang, False, False, 0)

        combo_lang = Gtk.ComboBoxText()
        combo_lang.append("auto", f"🌐 {t('lang_auto')}")
        for code, name in SUPPORTED_LANGUAGES.items():
            combo_lang.append(code, f"{name} ({code.upper()})")

        cur_lang_cfg = self.config.get("language", "auto")
        combo_lang.set_active_id(cur_lang_cfg)

        def on_lang_changed(cb):
            sel_id = cb.get_active_id() or "auto"
            self.config.set("language", sel_id)
            set_language(sel_id)
            self.update_ui_language()

        combo_lang.connect("changed", on_lang_changed)
        box.pack_start(combo_lang, False, False, 0)

        # 0.1. Search Engine Selection
        title_engine = Gtk.Label(label=f"<b>🔍 {GLib.markup_escape_text(t('search_engine_lbl'))}</b>")
        title_engine.set_use_markup(True)
        title_engine.set_halign(Gtk.Align.START)
        box.pack_start(title_engine, False, False, 0)

        combo_engine = Gtk.ComboBoxText()
        for eid, einfo in SEARCH_ENGINES.items():
            combo_engine.append(eid, f"{einfo['icon']} {einfo['name']}")

        cur_engine = self.config.get("search_engine", "google")
        combo_engine.set_active_id(cur_engine)

        def on_engine_changed(cb):
            sel_eng = cb.get_active_id() or "google"
            self.config.set("search_engine", sel_eng)
            self.broadcast_search_engine_update()

        combo_engine.connect("changed", on_engine_changed)
        box.pack_start(combo_engine, False, False, 0)

        sep0 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep0, False, False, 4)

        # 1. Permanent Sidebar Toggle
        title_sidebar = Gtk.Label(label=f"<b>{t('sidebar_display')}</b>")
        title_sidebar.set_use_markup(True)
        title_sidebar.set_halign(Gtk.Align.START)
        box.pack_start(title_sidebar, False, False, 0)

        sb_check = Gtk.CheckButton(label=t('sidebar_enable_chk'))
        sb_check.set_active(self.config.get("sidebar_enabled", True))

        def on_sb_toggled(btn):
            enabled = btn.get_active()
            self.config.set("sidebar_enabled", enabled)
            if enabled:
                self.sidebar_box.show()
                self.icon_dock.show_all()
                self.content_paned.set_position(DOCK_WIDTH)
            else:
                self.sidebar_box.hide()
                self.content_paned.set_position(0)

        sb_check.connect("toggled", on_sb_toggled)
        box.pack_start(sb_check, False, False, 0)

        sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep1, False, False, 4)

        # 2. Managing existing sidebar items (with Delete buttons)
        title_items = Gtk.Label(label=f"<b>{t('sidebar_items')}</b>")
        title_items.set_use_markup(True)
        title_items.set_halign(Gtk.Align.START)
        box.pack_start(title_items, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(170)
        items_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scrolled.add(items_vbox)
        box.pack_start(scrolled, True, True, 0)

        integrations = self.config.get("integrations", {})
        for k, v in list(integrations.items()):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

            check = Gtk.CheckButton(label=f"{v.get('icon', '')} {v.get('name', '')}")
            check.set_active(v.get("enabled", True))
            check.set_tooltip_text(v.get("url", ""))

            def on_item_toggled(btn, item_key=k):
                self.config.settings["integrations"][item_key]["enabled"] = btn.get_active()
                self.config.save_settings()
                self.rebuild_icon_dock()

            check.connect("toggled", on_item_toggled)
            row.pack_start(check, True, True, 0)

            # Delete button
            btn_del = Gtk.Button(label="🗑️ Izbriši")
            btn_del.get_style_context().add_class("btn-delete")

            def on_item_deleted(btn, item_key=k, row_box=row):
                self.config.remove_integration(item_key)
                items_vbox.remove(row_box)
                self.rebuild_icon_dock()
                if self.active_sidebar_service == item_key:
                    self.close_sidebar_panel()

            btn_del.connect("clicked", on_item_deleted)
            row.pack_end(btn_del, False, False, 0)

            items_vbox.pack_start(row, False, False, 0)

        # 3. Add Page Button inside Settings
        btn_add_inline = Gtk.Button(label="➕ Dodaj novo spletno stran v stransko vrstico")
        btn_add_inline.get_style_context().add_class("nav-btn")
        btn_add_inline.connect("clicked", lambda b: [dialog.destroy(), self.open_add_page_dialog()])
        box.pack_start(btn_add_inline, False, False, 4)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep2, False, False, 4)

        # 4. Force Dark Mode Setting
        dark_check = Gtk.CheckButton(label="🌙 Prisili temni način na vseh spletnih straneh (Force Dark Mode)")
        dark_check.set_active(self.config.get("force_dark_mode", False))
        dark_check.connect("toggled", lambda b: self.toggle_dark_mode())
        box.pack_start(dark_check, False, False, 0)

        # 5. Virtual Keyboard Setting
        kb_check = Gtk.CheckButton(label="⌨️ Omogoči navidezno tipkovnico na zaslonu")
        kb_check.set_active(self.config.get("virtual_keyboard_enabled", False))
        kb_check.connect("toggled", lambda b: self.toggle_virtual_keyboard())
        box.pack_start(kb_check, False, False, 0)

        # 6. Customize Themes & UserScripts Button
        btn_custom = Gtk.Button(label="🧩 Prilagodi videz, barvne teme in uporabniške skripte")
        btn_custom.get_style_context().add_class("nav-btn")
        btn_custom.connect("clicked", lambda b: [dialog.destroy(), self.open_customizer_dialog()])
        box.pack_start(btn_custom, False, False, 2)

        sep3 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep3, False, False, 4)

        # 7. Clear Browsing Data Button (Privacy)
        btn_clear_data = Gtk.Button(label="🧹 Počisti zgodovino, piškotke in predpomnilnik (Ctrl+Shift+Del)")
        btn_clear_data.get_style_context().add_class("btn-delete")
        btn_clear_data.connect("clicked", lambda b: [dialog.destroy(), self.open_clear_data_dialog()])
        box.pack_start(btn_clear_data, False, False, 2)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def create_main_webview(self):
        self.webview_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.webview_stack = Gtk.Stack()
        self.webview_stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.webview_container.pack_start(self.webview_stack, True, True, 0)

    def setup_webview_settings(self, webview):
        # Set dark canvas background color instantly to eliminate white flashbang on load
        dark_bg = Gdk.RGBA()
        dark_bg.parse("#080c16")
        webview.set_background_color(dark_bg)

        settings = webview.get_settings()
        settings.set_enable_developer_extras(True)
        settings.set_enable_webaudio(True)
        settings.set_enable_webgl(True)
        settings.set_enable_media_stream(True)
        settings.set_enable_smooth_scrolling(True)
        settings.set_enable_html5_local_storage(True)
        settings.set_enable_html5_database(True)
        settings.set_enable_javascript(True)
        settings.set_enable_javascript_markup(True)
        settings.set_allow_modal_dialogs(True)
        settings.set_enable_encrypted_media(True)
        settings.set_user_agent(USER_AGENT)

    def create_keyboard_panel(self):
        self.keyboard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.keyboard_box.set_size_request(-1, 240)
        self.keyboard_box.set_no_show_all(True)

        self.kb_webview = WebKit2.WebView.new_with_context(self.web_context)
        self.setup_webview_settings(self.kb_webview)
        kb_path = os.path.join(BASE_DIR, "ui", "keyboard.html")
        self.kb_webview.load_uri(f"file://{kb_path}")

        kb_content_mgr = self.kb_webview.get_user_content_manager()
        kb_content_mgr.register_script_message_handler("safeerKeyboard")
        kb_content_mgr.connect("script-message-received::safeerKeyboard", self.on_keyboard_message)

        self.keyboard_box.pack_start(self.kb_webview, True, True, 0)

        # Check config: Privzeto IZKLOPLJENO
        is_kb_on = self.config.get("virtual_keyboard_enabled", False)
        if is_kb_on:
            self.keyboard_box.show_all()
        else:
            self.keyboard_box.hide()

    def toggle_virtual_keyboard(self, widget=None):
        new_state = self.config.toggle_virtual_keyboard()
        if new_state:
            self.keyboard_box.show_all()
            self.btn_keyboard.set_label("⌨️ Tipkovnica (Vklopljena)")
            self.btn_keyboard.get_style_context().add_class("active")
        else:
            self.keyboard_box.hide()
            self.btn_keyboard.set_label("⌨️ Tipkovnica")
            self.btn_keyboard.get_style_context().remove_class("active")

    def on_keyboard_message(self, content_mgr, js_result):
        try:
            val = js_result.get_js_value()
            json_str = val.to_json(0)
            data = json.loads(json_str)
            if data.get("action") == "close":
                self.toggle_virtual_keyboard()
            elif "key" in data:
                key = data["key"]
                js_inject = """
                (function() {
                    const el = document.activeElement;
                    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) {
                        if ('__KEY__' === 'Backspace') {
                            el.value = el.value.slice(0, -1);
                        } else if ('__KEY__' === 'Enter') {
                            if (el.form) el.form.submit();
                        } else {
                            el.value = (el.value || '') + '__KEY__';
                        }
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                })();
                """.replace("__KEY__", key.replace("'", "\\'"))
                wv = self.get_active_webview()
                if wv:
                    wv.run_javascript(js_inject, None, None, None)
        except Exception as e:
            print(f"[Keyboard] Napaka: {e}")

    def load_homepage(self):
        home_path = os.path.join(BASE_DIR, "ui", "home.html")
        wv = self.get_active_webview()
        if wv:
            wv.load_uri(f"file://{home_path}")
        self.url_entry.set_text("safeer://home")
        active = self.get_active_tab()
        if active:
            active["title"] = "Safeer Domača Stran"
            active["icon"] = "🍃"
            active["title_label"].set_text("Safeer Domača Stran")
            active["icon_label"].set_text("🍃")
        self.security_icon.set_text("🎚️")

    def on_url_activate(self, entry):
        text = entry.get_text().strip()
        if not text:
            return

        # 1. Switch-To-Tab shortcut (npr. "% youtube" ali "% 24ur")
        if text.startswith("%") or text.startswith("@tab "):
            query = text.lstrip("%").replace("@tab", "").strip().lower()
            if query:
                for tab in self.tabs:
                    t_title = tab.get("title", "").lower()
                    t_uri = tab.get("uri", "").lower()
                    if query in t_title or query in t_uri:
                        self.switch_to_tab(tab["id"])
                        return

        # 2. Smart Search Engine prefixes (@g, @ddg, @b, @yt, @w, @gh)
        if text.startswith("@"):
            parts = text.split(" ", 1)
            prefix = parts[0].lower()
            q = parts[1].strip() if len(parts) > 1 else ""
            target = None
            if prefix in ("@g", "@google"):
                target = f"https://www.google.com/search?q={urllib.parse.quote_plus(q)}"
            elif prefix in ("@ddg", "@duckduckgo"):
                target = f"https://duckduckgo.com/?q={urllib.parse.quote_plus(q)}"
            elif prefix in ("@b", "@brave"):
                target = f"https://search.brave.com/search?q={urllib.parse.quote_plus(q)}"
            elif prefix in ("@yt", "@youtube"):
                target = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}"
            elif prefix in ("@w", "@wiki", "@wikipedia"):
                target = f"https://en.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote_plus(q)}"
            elif prefix in ("@gh", "@github"):
                target = f"https://github.com/search?q={urllib.parse.quote_plus(q)}"
            if target and q:
                wv = self.get_active_webview()
                if wv:
                    wv.load_uri(target)
                return

        if text == "safeer://home" or text == "about:blank":
            self.load_homepage()
            return

        if is_threat_domain(text):
            self.show_threat_warning(text)
            return

        if text.startswith("localhost:") or text == "localhost" or text.startswith("127.0.0.1:") or text == "127.0.0.1":
            target = "http://" + text
        elif text.startswith("file://"):
            target = text
        elif not text.startswith("http://") and not text.startswith("https://"):
            if "." in text and " " not in text:
                target = "https://" + text
            else:
                engine = self.config.get("search_engine", "google")
                engine_info = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["google"])
                target = f"{engine_info['url']}{urllib.parse.quote_plus(text)}"
        else:
            target = text

        wv = self.get_active_webview()
        if wv:
            wv.load_uri(target)

    def show_threat_warning(self, domain):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="🛡️ Safeer Shield: ZAZNANA NEVARNA DOMENA!"
        )
        dialog.format_secondary_text(
            f"Povezava z '{domain}' je bila prekinjena.\n"
            "abuse.ch C2 Botnet zaščita je preprečila zlonamerno komunikacijo."
        )
        dialog.run()
        dialog.destroy()

    def format_clean_url(self, uri):
        """Pretvori tehnični URL v čist, velik in jasno viden naslov kot v Mozilli Firefox."""
        if not uri or "ui/home.html" in uri:
            return "safeer://home"
        try:
            parsed = urllib.parse.urlparse(uri)
            if parsed.scheme in ("http", "https"):
                path = parsed.path if parsed.path and parsed.path != "/" else ""
                query = f"?{parsed.query}" if parsed.query else ""
                return f"{parsed.netloc}{path}{query}"
        except Exception:
            pass
        return uri

    def on_url_focus_in(self, entry, event):
        """Ob kliku v URL vrstico prikaži polni naslov in označi vse besedilo za urejanje."""
        wv = self.get_active_webview()
        cur_uri = wv.get_uri() if wv else ""
        if "ui/home.html" not in cur_uri and cur_uri:
            entry.set_text(cur_uri)
            GLib.idle_add(entry.select_region, 0, -1)
        return False

    def on_url_focus_out(self, entry, event):
        """Ko uporabnik klikne ven, vrni jasen, čist in berljiv naslov kot v Firefoxu."""
        wv = self.get_active_webview()
        cur_uri = wv.get_uri() if wv else ""
        if "ui/home.html" not in cur_uri and cur_uri:
            entry.set_text(self.format_clean_url(cur_uri))
        return False

    # -------------------------------------------------------------
    # Multi-Tab Management Engine
    # -------------------------------------------------------------
    def get_active_tab(self):
        for t in self.tabs:
            if t["id"] == self.active_tab_id:
                return t
        if self.tabs:
            return self.tabs[0]
        return None

    def get_active_webview(self):
        tab = self.get_active_tab()
        return tab["webview"] if tab else None

    def new_tab(self, url=None, switch=True):
        self.tab_counter += 1
        tab_id = f"tab_{self.tab_counter}"

        wv = WebKit2.WebView.new_with_context(self.web_context)
        self.setup_webview_settings(wv)

        wv.connect("load-changed", lambda w, ev: self.on_tab_load_changed(tab_id, w, ev))
        wv.connect("notify::title", lambda w, p: self.on_tab_title_changed(tab_id, w, p))
        wv.connect("notify::uri", lambda w, p: self.on_tab_uri_changed(tab_id, w, p))
        wv.connect("create", self.on_create_webview)
        wv.connect("decide-policy", self.on_decide_policy)

        content_mgr = wv.get_user_content_manager()
        content_mgr.register_script_message_handler("safeer")
        content_mgr.connect("script-message-received::safeer", self.on_js_message)

        # YouTube Adblock script
        yt_script = WebKit2.UserScript(
            YOUTUBE_ADBLOCK_SCRIPT,
            WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.START,
            ["*://*.youtube.com/*", "*://youtube.com/*", "*://*.googlevideo.com/*"],
            None
        )
        content_mgr.add_script(yt_script)

        # Cosmetic script
        gen_script = WebKit2.UserScript(
            GENERIC_COSMETIC_SCRIPT,
            WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.END,
            None,
            ["*://*.google.com/*", "*://*.google.si/*", "*://*.facebook.com/*", "*://*.messenger.com/*", "*://accounts.google.com/*", "*://*.banka.si/*"]
        )
        content_mgr.add_script(gen_script)

        # Custom User Scripts Injection (Tampermonkey Engine)
        user_scripts = self.config.get_user_scripts()
        for s in user_scripts:
            if s.get("enabled", True) and s.get("code"):
                try:
                    pattern = s.get("pattern", "*").strip()
                    whitelist = None if pattern in ("*", "") else [pattern if pattern.startswith("*://") or pattern.startswith("http") else f"*://*.{pattern}/*"]
                    run_time = WebKit2.UserScriptInjectionTime.START if s.get("run_at") == "start" else WebKit2.UserScriptInjectionTime.END
                    us = WebKit2.UserScript(
                        s["code"],
                        WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                        run_time,
                        whitelist,
                        None
                    )
                    content_mgr.add_script(us)
                except Exception as e:
                    print(f"[UserScript] Opozorilo pri nalaganju skripte '{s.get('name')}': {e}")

        # Force Dark Mode if enabled
        if self.config.get("force_dark_mode", False):
            self.apply_dark_mode_to_webview(wv, True)

        # Tab Strip Widget
        tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tab_box.get_style_context().add_class("firefox-tab")
        tab_box.get_style_context().add_class("inactive-tab")
        tab_box.set_size_request(200, 36)

        tab_icon = Gtk.Label(label="🌐")
        tab_icon.get_style_context().add_class("tab-icon")
        tab_box.pack_start(tab_icon, False, False, 2)

        tab_title = Gtk.Label(label="Nova stran")
        tab_title.get_style_context().add_class("tab-title")
        tab_title.set_ellipsize(Pango.EllipsizeMode.END)
        tab_title.set_xalign(0.0)
        tab_box.pack_start(tab_title, True, True, 2)

        # Audio Indicator & One-Click Mute Button (🔊 / 🔇)
        btn_audio = Gtk.Button(label="🔊")
        btn_audio.get_style_context().add_class("tab-audio-btn")
        btn_audio.set_tooltip_text(f"{t('audio_mute')}")
        btn_audio.set_no_show_all(True)
        btn_audio.hide()

        def on_tab_mute_clicked(b, w=wv, btn=btn_audio):
            muted = not w.get_property("is-muted")
            w.set_is_muted(muted)
            btn.set_label("🔇" if muted else "🔊")
            btn.set_tooltip_text(t("audio_unmute") if muted else t("audio_mute"))

        btn_audio.connect("clicked", on_tab_mute_clicked)
        tab_box.pack_start(btn_audio, False, False, 2)

        def on_audio_state_notify(w, param, btn=btn_audio):
            playing = w.get_property("is-playing-audio")
            muted = w.get_property("is-muted")
            if playing or muted:
                btn.set_label("🔇" if muted else "🔊")
                btn.set_tooltip_text(t("audio_unmute") if muted else t("audio_mute"))
                btn.show()
            else:
                btn.hide()

        wv.connect("notify::is-playing-audio", on_audio_state_notify)
        wv.connect("notify::is-muted", on_audio_state_notify)

        btn_close = Gtk.Button(label="✕")
        btn_close.get_style_context().add_class("tab-close-btn")
        btn_close.set_tooltip_text("Zapri zavihek (Ctrl + W)")
        btn_close.connect("clicked", lambda b: self.close_tab(tab_id))
        tab_box.pack_start(btn_close, False, False, 2)

        def on_tab_press(w, ev, tid=tab_id):
            if ev.button == 2:  # Srednji klik (kolešček) zapre zavihek
                self.close_tab(tid)
                return True
            elif ev.button == 1:
                self.switch_to_tab(tid)
                return True
            return False

        tab_event_box = Gtk.EventBox()
        tab_event_box.add(tab_box)
        tab_event_box.connect("button-press-event", on_tab_press)

        self.tabs_box.pack_start(tab_event_box, False, False, 0)
        tab_event_box.show_all()

        wv.show_all()
        self.webview_stack.add_named(wv, tab_id)

        tab_data = {
            "id": tab_id,
            "webview": wv,
            "title": "Nova stran",
            "icon": "🌐",
            "uri": url or "safeer://home",
            "tab_box": tab_box,
            "event_box": tab_event_box,
            "title_label": tab_title,
            "icon_label": tab_icon
        }
        self.tabs.append(tab_data)

        target = url or "safeer://home"
        if target == "safeer://home":
            home_path = os.path.join(BASE_DIR, "ui", "home.html")
            wv.load_uri(f"file://{home_path}")
            tab_title.set_text("Safeer Domača Stran")
            tab_icon.set_text("🍃")
        else:
            wv.load_uri(target)

        if switch:
            self.switch_to_tab(tab_id)

        return tab_id

    def close_tab(self, tab_id):
        tab_to_close = None
        for t in self.tabs:
            if t["id"] == tab_id:
                tab_to_close = t
                break
        if not tab_to_close:
            return

        if len(self.tabs) <= 1:
            self.load_homepage()
            return

        idx = self.tabs.index(tab_to_close)
        self.tabs.remove(tab_to_close)

        self.tabs_box.remove(tab_to_close["event_box"])
        self.webview_stack.remove(tab_to_close["webview"])
        tab_to_close["webview"].destroy()

        if self.active_tab_id == tab_id:
            new_idx = max(0, idx - 1)
            self.switch_to_tab(self.tabs[new_idx]["id"])

    def switch_to_tab(self, tab_id):
        self.active_tab_id = tab_id
        target = None
        for t in self.tabs:
            if t["id"] == tab_id:
                target = t
                t["tab_box"].get_style_context().add_class("active-tab")
                t["tab_box"].get_style_context().remove_class("inactive-tab")
            else:
                t["tab_box"].get_style_context().remove_class("active-tab")
                t["tab_box"].get_style_context().add_class("inactive-tab")

        if not target:
            return

        self.webview_stack.set_visible_child(target["webview"])

        cur_uri = target["webview"].get_uri() or target["uri"] or ""
        self.url_entry.set_text(self.format_clean_url(cur_uri))
        if cur_uri.startswith("https://"):
            self.security_icon.set_text("🔒")
        else:
            self.security_icon.set_text("🎚️")

        self.set_title(f"{target['title']} — Safeer Browser (Linux Mint)")
        self.update_star_status()

    def on_tab_load_changed(self, tab_id, webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            uri = webview.get_uri() or ""
            title = webview.get_title() or ""

            for t in self.tabs:
                if t["id"] == tab_id:
                    t["uri"] = uri
                    if "ui/home.html" in uri:
                        h_title = t("home_title")
                        t["title"] = h_title
                        t["icon"] = "🍃"
                        if "title_label" in t and t["title_label"]:
                            t["title_label"].set_text(h_title)
                        if "icon_label" in t and t["icon_label"]:
                            t["icon_label"].set_text("🍃")
                        # Inject live custom portals into home.html
                        portals = self.config.get_portals()
                        portals_json = json.dumps(portals)
                        lang = get_current_language()
                        js = f"if (window.setCustomPortals) {{ window.setCustomPortals({portals_json}); }} if (window.setAppLanguage) {{ window.setAppLanguage('{lang}'); }}"
                        webview.run_javascript(js, None, None, None)
                    break

            if self.active_tab_id == tab_id:
                if "ui/home.html" in uri:
                    self.url_entry.set_text("safeer://home")
                    self.security_icon.set_text("🎚️")
                else:
                    self.url_entry.set_text(self.format_clean_url(uri))
                    if uri.startswith("https://"):
                        self.security_icon.set_text("🔒")
                    else:
                        self.security_icon.set_text("🎚️")
                self.update_star_status()

            self.add_history_entry(uri, title)

            if self.config.get("force_dark_mode", False) and "ui/home.html" not in uri:
                self.inject_dark_mode_js(webview, True)

    def on_tab_title_changed(self, tab_id, webview, prop):
        title = webview.get_title()
        if not title:
            return

        for t in self.tabs:
            if t["id"] == tab_id:
                t["title"] = title
                t["title_label"].set_text(title)
                t_lower = title.lower()
                if "google" in t_lower:
                    t["icon_label"].set_text("🌐")
                elif "youtube" in t_lower:
                    t["icon_label"].set_text("▶️")
                elif "facebook" in t_lower or "messenger" in t_lower:
                    t["icon_label"].set_text("💬")
                elif "gmail" in t_lower or "pošta" in t_lower:
                    t["icon_label"].set_text("✉️")
                else:
                    t["icon_label"].set_text("🌐")
                break

        if self.active_tab_id == tab_id:
            self.set_title(f"{title} — Safeer Browser (Linux Mint)")

    def on_tab_uri_changed(self, tab_id, webview, prop):
        uri = webview.get_uri()
        if uri and "ui/home.html" not in uri:
            for t in self.tabs:
                if t["id"] == tab_id:
                    t["uri"] = uri
                    break
            if self.active_tab_id == tab_id and not self.url_entry.is_focus():
                self.url_entry.set_text(self.format_clean_url(uri))
                self.update_star_status()


    # -------------------------------------------------------------
    # Force Dark Mode Engine
    # -------------------------------------------------------------
    def apply_dark_mode_to_webview(self, webview, is_dark: bool):
        content_mgr = webview.get_user_content_manager()
        try:
            content_mgr.remove_all_style_sheets()
        except Exception:
            pass

        if is_dark:
            try:
                sheet = WebKit2.UserStyleSheet(
                    FORCE_DARK_MODE_CSS,
                    WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                    WebKit2.UserStyleLevel.USER,
                    None,
                    ["file://*"]
                )
                content_mgr.add_style_sheet(sheet)
            except Exception as e:
                print(f"[DarkMode] Napaka: {e}")

    def toggle_dark_mode(self, widget=None):
        new_state = self.config.toggle_force_dark()
        self.update_dark_mode_ui(new_state)

    def update_dark_mode_ui(self, is_dark: bool):
        if hasattr(self, 'btn_dark_mode'):
            if is_dark:
                self.btn_dark_mode.set_label("🌙")
                self.btn_dark_mode.get_style_context().add_class("active")
                self.btn_dark_mode.set_tooltip_text("Prisili temni način (Force Dark Mode) — VKLOPLJEN")
            else:
                self.btn_dark_mode.set_label("☀️")
                self.btn_dark_mode.get_style_context().remove_class("active")
                self.btn_dark_mode.set_tooltip_text("Prisili temni način (Force Dark Mode) — IZKLOPLJEN")

        for tab in self.tabs:
            wv = tab["webview"]
            self.apply_dark_mode_to_webview(wv, is_dark)
            self.inject_dark_mode_js(wv, is_dark)

    def inject_dark_mode_js(self, webview, is_dark: bool):
        js = f"""
        (function() {{
            if (window.location.protocol === 'file:') return;
            var el = document.getElementById('safeer-force-dark-style');
            var enable = {'true' if is_dark else 'false'};
            if (enable) {{
                if (!el) {{
                    el = document.createElement('style');
                    el.id = 'safeer-force-dark-style';
                    el.textContent = `{FORCE_DARK_MODE_CSS.strip()}`;
                    (document.head || document.documentElement).appendChild(el);
                }}
            }} else {{
                if (el) el.remove();
            }}
        }})();
        """
        try:
            webview.run_javascript(js, None, None, None)
        except Exception:
            pass

    # -------------------------------------------------------------
    # Downloads Management Engine
    # -------------------------------------------------------------
    def setup_downloads_handling(self):
        self.web_context.connect("download-started", self.on_download_started)

    def on_download_started(self, context, download):
        dl_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or os.path.expanduser("~/Prejemi")
        os.makedirs(dl_dir, exist_ok=True)

        req = download.get_request()
        uri = req.get_uri() if req else ""
        suggested = download.get_response().get_suggested_filename() if download.get_response() else ""
        if not suggested:
            suggested = os.path.basename(urllib.parse.urlparse(uri).path) or "prenos_datoteke"

        target_path = os.path.join(dl_dir, suggested)
        base, ext = os.path.splitext(suggested)
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(dl_dir, f"{base}_{counter}{ext}")
            counter += 1

        dest_uri = f"file://{target_path}"
        download.set_destination(dest_uri)

        dl_data = {
            "id": str(uuid.uuid4())[:8],
            "filename": os.path.basename(target_path),
            "path": target_path,
            "progress": 0.0,
            "status": "running",
            "time": datetime.now().strftime("%H:%M:%S")
        }
        self.downloads.insert(0, dl_data)

        self.btn_downloads.set_label("⬇️ 0%")
        self.btn_downloads.get_style_context().add_class("active")

        download.connect("notify::estimated-progress", lambda d, p: self.on_download_progress(dl_data, d))
        download.connect("finished", lambda d: self.on_download_finished(dl_data))
        download.connect("failed", lambda d, err: self.on_download_failed(dl_data, err))

    def on_download_progress(self, dl_data, download):
        prog = download.get_estimated_progress()
        dl_data["progress"] = prog
        pct = int(prog * 100)
        self.btn_downloads.set_label(f"⬇️ {pct}%")

    def on_download_finished(self, dl_data):
        dl_data["status"] = "completed"
        dl_data["progress"] = 1.0
        any_running = any(d["status"] == "running" for d in self.downloads)
        if not any_running:
            self.btn_downloads.set_label("📥")
            self.btn_downloads.get_style_context().remove_class("active")

    def on_download_failed(self, dl_data, error):
        dl_data["status"] = "failed"
        any_running = any(d["status"] == "running" for d in self.downloads)
        if not any_running:
            self.btn_downloads.set_label("📥")
            self.btn_downloads.get_style_context().remove_class("active")

    def open_downloads_dialog(self):
        dialog = Gtk.Dialog(title=f"📥 {t('downloads_title')} — Safeer Browser", transient_for=self, flags=0)
        dialog.set_default_size(600, 460)
        dialog.get_style_context().add_class("customizer-dialog")
        btn_close = dialog.add_button(t("close", "Zapri"), Gtk.ResponseType.CLOSE)
        btn_close.get_style_context().add_class("customizer-close-btn")

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(14)
        content.set_margin_bottom(14)
        content.set_margin_left(16)
        content.set_margin_right(16)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_title = Gtk.Label(label=f"<b><span size='11500'>{GLib.markup_escape_text(t('active_recent_downloads'))}</span></b>")
        lbl_title.set_use_markup(True)
        lbl_title.set_xalign(0.0)
        header_box.pack_start(lbl_title, True, True, 0)

        btn_open_folder = Gtk.Button(label=t("open_downloads_folder"))
        btn_open_folder.get_style_context().add_class("btn-primary-glow")
        dl_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or os.path.expanduser("~/Prejemi")
        btn_open_folder.connect("clicked", lambda b: subprocess.Popen(["xdg-open", dl_dir]))
        header_box.pack_start(btn_open_folder, False, False, 0)
        content.pack_start(header_box, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content.pack_start(scroll, True, True, 0)

        dls_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scroll.add(dls_vbox)

        if not self.downloads:
            empty_lbl = Gtk.Label(label=t("no_downloads"))
            empty_lbl.get_style_context().add_class("text-muted")
            dls_vbox.pack_start(empty_lbl, True, True, 20)
        else:
            for dl in self.downloads:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                row.get_style_context().add_class("item-card-row")

                icon_lbl = Gtk.Label(label="✅" if dl["status"] == "completed" else ("⬇️" if dl["status"] == "running" else "❌"))
                row.pack_start(icon_lbl, False, False, 4)

                meta_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                fname_lbl = Gtk.Label(label=f"<b>{GLib.markup_escape_text(dl['filename'])}</b>")
                fname_lbl.set_use_markup(True)
                fname_lbl.set_xalign(0.0)
                fname_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                meta_box.pack_start(fname_lbl, False, False, 0)

                status_name = t("dl_completed") if dl["status"] == "completed" else (f"{t('dl_downloading')} {int(dl['progress']*100)}%" if dl["status"] == "running" else t("dl_failed"))
                status_txt = f"{dl['time']} • {status_name}"
                status_lbl = Gtk.Label(label=status_txt)
                status_lbl.set_xalign(0.0)
                status_lbl.get_style_context().add_class("text-muted")
                meta_box.pack_start(status_lbl, False, False, 0)
                row.pack_start(meta_box, True, True, 0)

                if dl["status"] == "completed" and os.path.exists(dl["path"]):
                    btn_open = Gtk.Button(label=t("open_file"))
                    btn_open.get_style_context().add_class("nav-btn")
                    p = dl["path"]
                    btn_open.connect("clicked", lambda b, path=p: subprocess.Popen(["xdg-open", path]))
                    row.pack_end(btn_open, False, False, 0)

                dls_vbox.pack_start(row, False, False, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    # -------------------------------------------------------------
    # History Management Engine
    # -------------------------------------------------------------
    def add_history_entry(self, uri, title):
        if not uri or "ui/home.html" in uri or uri == "safeer://home" or uri == "about:blank":
            return
        entry = {
            "title": title or uri,
            "url": uri,
            "time": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        history = self.load_history()
        if history and history[0].get("url") == uri:
            history[0]["title"] = entry["title"]
            history[0]["time"] = entry["time"]
        else:
            history.insert(0, entry)
        history = history[:500]
        self.save_history(history)

    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def save_history(self, history):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def open_history_dialog(self):
        dialog = Gtk.Dialog(title=f"🕒 {t('history_title')} — Safeer Browser", transient_for=self, flags=0)
        dialog.set_default_size(720, 500)
        dialog.get_style_context().add_class("customizer-dialog")
        btn_close = dialog.add_button(t("close", "Zapri"), Gtk.ResponseType.CLOSE)
        btn_close.get_style_context().add_class("customizer-close-btn")

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(14)
        content.set_margin_bottom(14)
        content.set_margin_left(16)
        content.set_margin_right(16)

        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search_entry = Gtk.Entry()
        search_entry.set_placeholder_text(t("search_history_placeholder"))
        search_entry.get_style_context().add_class("ff-url-entry")
        top_box.pack_start(search_entry, True, True, 0)

        btn_clear = Gtk.Button(label=t("clear_history"))
        btn_clear.get_style_context().add_class("btn-delete")
        top_box.pack_start(btn_clear, False, False, 0)

        btn_clear_cookies = Gtk.Button(label=t("cookies_data"))
        btn_clear_cookies.get_style_context().add_class("nav-btn")
        btn_clear_cookies.connect("clicked", lambda b: [dialog.destroy(), self.open_clear_data_dialog()])
        top_box.pack_start(btn_clear_cookies, False, False, 0)
        content.pack_start(top_box, False, False, 0)

        store = Gtk.ListStore(str, str, str)
        all_history = self.load_history()
        for item in all_history:
            store.append([item.get("time", ""), item.get("title", ""), item.get("url", "")])

        filter_store = store.filter_new()
        def search_filter_func(model, iter, data):
            query = search_entry.get_text().lower().strip()
            if not query:
                return True
            title = model[iter][1].lower()
            url = model[iter][2].lower()
            return query in title or query in url

        filter_store.set_visible_func(search_filter_func)
        search_entry.connect("changed", lambda e: filter_store.refilter())

        tree = Gtk.TreeView(model=filter_store)
        tree.get_style_context().add_class("history-tree")

        col_time = Gtk.TreeViewColumn(t("history_time_col"), Gtk.CellRendererText(), text=0)
        col_time.set_min_width(130)
        tree.append_column(col_time)

        col_title = Gtk.TreeViewColumn(t("history_title_col"), Gtk.CellRendererText(), text=1)
        col_title.set_min_width(240)
        tree.append_column(col_title)

        col_url = Gtk.TreeViewColumn(t("history_url_col"), Gtk.CellRendererText(), text=2)
        col_url.set_min_width(280)
        tree.append_column(col_url)

        def on_row_activated(treeview, path, column):
            model = treeview.get_model()
            url = model[path][2]
            if url:
                wv = self.get_active_webview()
                if wv:
                    wv.load_uri(url)
                dialog.destroy()

        tree.connect("row-activated", on_row_activated)

        def on_clear_clicked(btn):
            self.save_history([])
            store.clear()

        btn_clear.connect("clicked", on_clear_clicked)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(tree)
        content.pack_start(scroll, True, True, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def open_clear_data_dialog(self):
        """Dialog za brisanje zgodovine, piškotkov, prijavnih sej in predpomnilnika."""
        dialog = Gtk.Dialog(
            title=f"🧹 {t('clear_data_title')} — Safeer Browser",
            transient_for=self,
            flags=0
        )
        dialog.set_default_size(500, 340)
        dialog.get_style_context().add_class("customizer-dialog")
        btn_cancel = dialog.add_button(t("cancel", "Prekliči"), Gtk.ResponseType.CANCEL)
        btn_cancel.get_style_context().add_class("customizer-close-btn")
        btn_confirm = dialog.add_button(t("clear_selected_btn"), Gtk.ResponseType.OK)
        btn_confirm.get_style_context().add_class("btn-delete")

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_left(20)
        content.set_margin_right(20)

        header = Gtk.Label(label=f"<b>{GLib.markup_escape_text(t('clear_data_header'))}</b>")
        header.set_use_markup(True)
        header.set_xalign(0.0)
        content.pack_start(header, False, False, 0)

        check_history = Gtk.CheckButton(label=t("clear_history_chk"))
        check_history.set_active(True)
        content.pack_start(check_history, False, False, 2)

        check_cookies = Gtk.CheckButton(label=t("clear_cookies_chk"))
        check_cookies.set_active(True)
        content.pack_start(check_cookies, False, False, 2)

        check_cache = Gtk.CheckButton(label=t("clear_cache_chk"))
        check_cache.set_active(True)
        content.pack_start(check_cache, False, False, 2)

        dialog.show_all()
        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            do_hist = check_history.get_active()
            do_cookies = check_cookies.get_active()
            do_cache = check_cache.get_active()

            if do_hist:
                self.save_history([])

            types_to_clear = 0
            if do_cookies:
                types_to_clear |= WebKit2.WebsiteDataTypes.COOKIES
                types_to_clear |= WebKit2.WebsiteDataTypes.SESSION_STORAGE
                types_to_clear |= WebKit2.WebsiteDataTypes.LOCAL_STORAGE
                cookie_path = os.path.join(self.config.config_dir, "cookies.sqlite")
                if os.path.exists(cookie_path):
                    try:
                        os.remove(cookie_path)
                    except Exception:
                        pass

            if do_cache:
                types_to_clear |= WebKit2.WebsiteDataTypes.DISK_CACHE
                types_to_clear |= WebKit2.WebsiteDataTypes.MEMORY_CACHE
                types_to_clear |= WebKit2.WebsiteDataTypes.DOM_CACHE
                types_to_clear |= WebKit2.WebsiteDataTypes.INDEXEDDB_DATABASES
                types_to_clear |= WebKit2.WebsiteDataTypes.WEBSQL_DATABASES
                types_to_clear |= WebKit2.WebsiteDataTypes.OFFLINE_APPLICATION_CACHE

            if types_to_clear != 0:
                try:
                    self.website_data_manager.clear(types_to_clear, 0, None, None, None)
                except Exception as e:
                    print(f"[ClearData] Napaka: {e}")

        dialog.destroy()

    def open_customizer_dialog(self):
        """Dialog za prilagoditev teme, lastnega CSS-ja in uporabniških skript (Tampermonkey)."""
        dialog = Gtk.Dialog(
            title=f"🧩 {t('customizer_title')} — Safeer",
            transient_for=self,
            flags=0
        )
        dialog.set_default_size(940, 680)
        dialog.set_resizable(True)
        dialog.set_position(Gtk.WindowPosition.CENTER)
        dialog.get_style_context().add_class("customizer-dialog")

        btn_close = dialog.add_button(t("close", "Zapri"), Gtk.ResponseType.CLOSE)
        btn_close.get_style_context().add_class("customizer-close-btn")

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(16)
        content.set_margin_end(16)

        # -------------------------------------------------------------
        # Hero Header Banner
        # -------------------------------------------------------------
        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        banner.get_style_context().add_class("customizer-banner")

        icon_lbl = Gtk.Label(label="✨")
        icon_lbl.get_style_context().add_class("banner-icon")
        banner.pack_start(icon_lbl, False, False, 2)

        title_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_head = Gtk.Label(label=f"<b><span size='13000'>{GLib.markup_escape_text(t('customizer_title'))}</span></b>")
        lbl_head.set_use_markup(True)
        lbl_head.set_xalign(0.0)

        lbl_sub = Gtk.Label(label=f"<span color='#94a3b8'>{GLib.markup_escape_text(t('customizer_subtitle'))}</span>")
        lbl_sub.set_use_markup(True)
        lbl_sub.set_xalign(0.0)

        title_vbox.pack_start(lbl_head, False, False, 0)
        title_vbox.pack_start(lbl_sub, False, False, 0)
        banner.pack_start(title_vbox, True, True, 0)
        content.pack_start(banner, False, False, 0)

        notebook = Gtk.Notebook()
        notebook.get_style_context().add_class("customizer-notebook")
        notebook.set_vexpand(True)
        notebook.set_hexpand(True)
        content.pack_start(notebook, True, True, 0)

        # -------------------------------------------------------------
        # ZAVIHEK 1: 🎨 Teme & Barve (Interaktivne Tematske Kartice)
        # -------------------------------------------------------------
        themes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        themes_box.set_margin_top(16)
        themes_box.set_margin_bottom(16)
        themes_box.set_margin_start(16)
        themes_box.set_margin_end(16)

        lbl_theme = Gtk.Label(label=f"<b><span size='11500'>{GLib.markup_escape_text(t('choose_theme'))}</span></b>")
        lbl_theme.set_use_markup(True)
        lbl_theme.set_xalign(0.0)
        themes_box.pack_start(lbl_theme, False, False, 0)

        grid = Gtk.Grid()
        grid.set_column_spacing(14)
        grid.set_row_spacing(14)
        grid.set_hexpand(True)
        grid.set_column_homogeneous(True)

        theme_cards_data = [
            {
                "id": "midnight",
                "name": "Firefox Midnight",
                "icon": "🌙",
                "desc": t("theme_midnight_desc"),
                "tag": "Proton • Dark",
                "colors": ["#1c1b22", "#2b2a33", "#0060df"]
            },
            {
                "id": "mint",
                "name": "Linux Mint Emerald",
                "icon": "🍃",
                "desc": t("theme_mint_desc"),
                "tag": "Mint Desktop • Eco",
                "colors": ["#141c15", "#1c2b1f", "#87cf3e"]
            },
            {
                "id": "neon",
                "name": "Cyberpunk Neon",
                "icon": "⚡",
                "desc": t("theme_neon_desc"),
                "tag": "Cyan & Violet",
                "colors": ["#090d16", "#111827", "#00d2ff"]
            },
            {
                "id": "amoled",
                "name": "Pure AMOLED Black",
                "icon": "🖤",
                "desc": t("theme_amoled_desc"),
                "tag": "Pitch Black • OLED",
                "colors": ["#000000", "#181818", "#38bdf8"]
            }
        ]

        card_widgets = []
        cur_theme = self.config.get("theme", "midnight")

        def select_theme(th_id):
            self.config.set("theme", th_id)
            self.apply_css()
            for c_id, c_box, badge_lbl in card_widgets:
                is_active = (c_id == th_id)
                ctx = c_box.get_style_context()
                b_ctx = badge_lbl.get_style_context()
                if is_active:
                    ctx.add_class("active-theme")
                    b_ctx.add_class("active-badge")
                    badge_lbl.set_text(f"✓ {t('active_theme_badge')}")
                else:
                    ctx.remove_class("active-theme")
                    b_ctx.remove_class("active-badge")
                    badge_lbl.set_text(t("select_theme_btn"))

        for idx, th in enumerate(theme_cards_data):
            th_id = th["id"]
            is_cur = (cur_theme == th_id)

            eb = Gtk.EventBox()
            try:
                eb.set_cursor(Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "pointer"))
            except Exception:
                pass

            card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card_box.get_style_context().add_class("theme-card-box")
            if is_cur:
                card_box.get_style_context().add_class("active-theme")

            top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            t_lbl = Gtk.Label(label=f"<b>{th['icon']} {th['name']}</b>")
            t_lbl.set_use_markup(True)
            t_lbl.set_xalign(0.0)
            top_row.pack_start(t_lbl, True, True, 0)

            for hex_val in th["colors"]:
                sw = Gtk.Box()
                sw.set_size_request(13, 13)
                p = Gtk.CssProvider()
                p.load_from_data(f".swatch-{hex_val[1:]} {{ background-color: {hex_val}; border-radius: 50%; min-width: 12px; min-height: 12px; margin-right: 3px; border: 1px solid rgba(255,255,255,0.25); }}".encode('utf-8'))
                sw.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                sw.get_style_context().add_class(f"swatch-{hex_val[1:]}")
                top_row.pack_start(sw, False, False, 0)

            badge_lbl = Gtk.Label(label=f"✓ {t('active_theme_badge')}" if is_cur else t("select_theme_btn"))
            badge_lbl.get_style_context().add_class("theme-badge")
            if is_cur:
                badge_lbl.get_style_context().add_class("active-badge")
            top_row.pack_end(badge_lbl, False, False, 0)
            card_box.pack_start(top_row, False, False, 0)

            d_lbl = Gtk.Label(label=th["desc"])
            d_lbl.set_line_wrap(True)
            d_lbl.set_xalign(0.0)
            d_lbl.get_style_context().add_class("text-muted")
            card_box.pack_start(d_lbl, False, False, 0)

            tag_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            tag_lbl = Gtk.Label(label=f"<small>{GLib.markup_escape_text(th['tag'])}</small>")
            tag_lbl.set_use_markup(True)
            tag_lbl.get_style_context().add_class("theme-badge")
            tag_box.pack_start(tag_lbl, False, False, 0)
            card_box.pack_start(tag_box, False, False, 0)

            eb.add(card_box)
            eb.connect("button-press-event", lambda w, ev, tid=th_id: select_theme(tid))

            grid.attach(eb, idx % 2, idx // 2, 1, 1)
            card_widgets.append((th_id, card_box, badge_lbl))

        themes_box.pack_start(grid, False, False, 0)

        info_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        info_card.get_style_context().add_class("theme-card-box")
        info_card.set_margin_top(12)
        lbl_info = Gtk.Label(label=f"💡 <i>{GLib.markup_escape_text(t('theme_live_notice'))}</i>")
        lbl_info.set_use_markup(True)
        lbl_info.set_xalign(0.0)
        info_card.pack_start(lbl_info, True, True, 4)
        themes_box.pack_start(info_card, False, False, 0)

        notebook.append_page(themes_box, Gtk.Label(label=f"🎨 {t('tab_themes')}"))

        # -------------------------------------------------------------
        # ZAVIHEK 2: 🖌️ Lasten CSS (userChrome.css) - VELIK IN PROSTOREN!
        # -------------------------------------------------------------
        css_page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        css_page_box.set_margin_top(14)
        css_page_box.set_margin_bottom(14)
        css_page_box.set_margin_start(16)
        css_page_box.set_margin_end(16)
        css_page_box.set_vexpand(True)
        css_page_box.set_hexpand(True)

        css_header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_css_title = Gtk.Label(label=f"<b>{GLib.markup_escape_text(t('custom_css_title'))}</b>")
        lbl_css_title.set_use_markup(True)
        lbl_css_title.set_xalign(0.0)
        css_header_box.pack_start(lbl_css_title, True, True, 0)
        css_page_box.pack_start(css_header_box, False, False, 0)

        lbl_css_desc = Gtk.Label(label=t('custom_css_desc'))
        lbl_css_desc.set_xalign(0.0)
        css_page_box.pack_start(lbl_css_desc, False, False, 0)

        # Snippets Bar
        snippets_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_snip = Gtk.Label(label=f"<b>{GLib.markup_escape_text(t('snippets_lbl'))}</b>")
        lbl_snip.set_use_markup(True)
        snippets_box.pack_start(lbl_snip, False, False, 0)

        btn_snip_rounded = Gtk.Button(label=t('snip_rounded'))
        btn_snip_rounded.get_style_context().add_class("snippet-chip")
        btn_snip_font = Gtk.Button(label=t('snip_font'))
        btn_snip_font.get_style_context().add_class("snippet-chip")
        btn_snip_glow = Gtk.Button(label=t('snip_glow'))
        btn_snip_glow.get_style_context().add_class("snippet-chip")
        btn_snip_compact = Gtk.Button(label=t('snip_compact'))
        btn_snip_compact.get_style_context().add_class("snippet-chip")

        snippets_box.pack_start(btn_snip_rounded, False, False, 0)
        snippets_box.pack_start(btn_snip_font, False, False, 0)
        snippets_box.pack_start(btn_snip_glow, False, False, 0)
        snippets_box.pack_start(btn_snip_compact, False, False, 0)
        css_page_box.pack_start(snippets_box, False, False, 2)

        # Spacious Scrolled Code Editor
        css_scroll = Gtk.ScrolledWindow()
        css_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        css_scroll.set_vexpand(True)
        css_scroll.set_hexpand(True)
        css_scroll.set_min_content_height(340)

        css_tv = Gtk.TextView()
        css_tv.get_style_context().add_class("code-editor")
        css_tv.set_monospace(True)
        css_tv.set_vexpand(True)
        css_tv.set_hexpand(True)
        css_tv.set_left_margin(14)
        css_tv.set_right_margin(14)
        css_tv.set_top_margin(12)
        css_tv.set_bottom_margin(12)

        css_buf = css_tv.get_buffer()
        existing_css = self.config.get("custom_css", "")
        if not existing_css:
            existing_css = "/* Safeer Browser — Lasten CSS (userChrome.css slog) */\n/* Primer:\n.toolbar { background: #0c1017; }\n.nav-btn { border-radius: 8px; }\n*/\n"
        css_buf.set_text(existing_css)

        def insert_snippet(btn, snippet_code):
            cur_txt = css_buf.get_text(css_buf.get_start_iter(), css_buf.get_end_iter(), True)
            if snippet_code not in cur_txt:
                new_txt = cur_txt.rstrip() + "\n\n" + snippet_code + "\n"
                css_buf.set_text(new_txt)

        btn_snip_rounded.connect("clicked", insert_snippet, "/* Zaobljeni zavihki */\n.tab-btn { border-radius: 12px 12px 0 0; }")
        btn_snip_font.connect("clicked", insert_snippet, "/* Večja pisava */\n* { font-size: 14px; }")
        btn_snip_glow.connect("clicked", insert_snippet, "/* Cian sijaj */\n.url-bar:focus-within { box-shadow: 0 0 12px rgba(0, 210, 255, 0.4); }")
        btn_snip_compact.connect("clicked", insert_snippet, "/* Kompaktna orodna vrstica */\n.nav-btn { padding: 3px 6px; }")

        css_scroll.add(css_tv)
        css_page_box.pack_start(css_scroll, True, True, 0)

        # Action Buttons for CSS
        css_actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_save_css = Gtk.Button(label=t('save_and_apply_css'))
        btn_save_css.get_style_context().add_class("btn-primary-glow")
        def on_save_css(b):
            txt = css_buf.get_text(css_buf.get_start_iter(), css_buf.get_end_iter(), True)
            self.config.set("custom_css", txt)
            self.apply_css()
            orig_lbl = b.get_label()
            b.set_label("✅ OK!")
            GLib.timeout_add(1500, lambda: b.set_label(orig_lbl))
        btn_save_css.connect("clicked", on_save_css)
        css_actions_box.pack_start(btn_save_css, False, False, 0)

        btn_clear_css = Gtk.Button(label=t('clear_code'))
        btn_clear_css.get_style_context().add_class("btn-delete")
        def on_clear_css(b):
            css_buf.set_text("")
            self.config.set("custom_css", "")
            self.apply_css()
        btn_clear_css.connect("clicked", on_clear_css)
        css_actions_box.pack_end(btn_clear_css, False, False, 0)

        css_page_box.pack_start(css_actions_box, False, False, 0)

        notebook.append_page(css_page_box, Gtk.Label(label=f"🖌️ {t('tab_css')}"))

        # -------------------------------------------------------------
        # ZAVIHEK 3: ⭐ Priljubljene strani & Multimedija
        # -------------------------------------------------------------
        portals_tab_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        portals_tab_box.set_margin_top(14)
        portals_tab_box.set_margin_bottom(14)
        portals_tab_box.set_margin_start(16)
        portals_tab_box.set_margin_end(16)
        portals_tab_box.set_vexpand(True)
        portals_tab_box.set_hexpand(True)

        portals_top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_portals_head = Gtk.Label(label=f"<b><span size='11500'>{GLib.markup_escape_text(t('portals_title'))}</span></b>")
        lbl_portals_head.set_use_markup(True)
        lbl_portals_head.set_xalign(0.0)
        portals_top_bar.pack_start(lbl_portals_head, True, True, 0)

        btn_add_p_tab = Gtk.Button(label=f"➕ {t('add_portal')}")
        btn_add_p_tab.get_style_context().add_class("btn-primary-glow")
        portals_top_bar.pack_end(btn_add_p_tab, False, False, 0)

        btn_res_p_tab = Gtk.Button(label=f"🔄 {t('reset_default')}")
        btn_res_p_tab.get_style_context().add_class("btn-delete")
        portals_top_bar.pack_end(btn_res_p_tab, False, False, 0)
        portals_tab_box.pack_start(portals_top_bar, False, False, 0)

        p_scroll = Gtk.ScrolledWindow()
        p_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        p_scroll.set_vexpand(True)
        p_scroll.set_hexpand(True)
        p_scroll.set_min_content_height(340)

        p_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        p_scroll.add(p_list_box)
        portals_tab_box.pack_start(p_scroll, True, True, 0)

        def populate_tab_portals():
            for child in p_list_box.get_children():
                p_list_box.remove(child)

            portals = self.config.get_portals()
            for p in portals:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                row.get_style_context().add_class("item-card-row")

                badge = Gtk.Label(label=p.get("mark", "🌐"))
                badge.set_width_chars(3)
                badge.get_style_context().add_class("nav-btn")
                row.pack_start(badge, False, False, 4)

                info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                lbl_title = Gtk.Label(label=f"<b>{GLib.markup_escape_text(p.get('title', ''))}</b>")
                lbl_title.set_use_markup(True)
                lbl_title.set_xalign(0.0)
                lbl_url = Gtk.Label(label=p.get('url', ''))
                lbl_url.set_xalign(0.0)
                lbl_url.get_style_context().add_class("text-muted")
                info_box.pack_start(lbl_title, False, False, 0)
                info_box.pack_start(lbl_url, False, False, 0)
                row.pack_start(info_box, True, True, 0)

                btn_edit = Gtk.Button(label=f"✏️ {t('edit')}")
                btn_edit.get_style_context().add_class("nav-btn")
                btn_edit.connect("clicked", lambda b, prt=p: self.open_portal_editor_dialog(prt, on_saved=populate_tab_portals))
                row.pack_end(btn_edit, False, False, 4)

                btn_del = Gtk.Button(label="🗑️")
                btn_del.get_style_context().add_class("btn-delete")
                def on_delete_tab(b, pid=p.get("id")):
                    self.config.delete_portal(pid)
                    self.broadcast_portals_update()
                    populate_tab_portals()
                btn_del.connect("clicked", on_delete_tab)
                row.pack_end(btn_del, False, False, 0)

                p_list_box.pack_start(row, False, False, 0)

            p_list_box.show_all()

        populate_tab_portals()
        btn_add_p_tab.connect("clicked", lambda b: self.open_portal_editor_dialog(None, on_saved=populate_tab_portals))
        def on_reset_tab_click(b):
            self.config.reset_portals()
            self.broadcast_portals_update()
            populate_tab_portals()
        btn_res_p_tab.connect("clicked", on_reset_tab_click)

        notebook.append_page(portals_tab_box, Gtk.Label(label=f"⭐ {t('tab_portals')}"))

        # -------------------------------------------------------------
        # ZAVIHEK 4: 🧩 Uporabniške skripte (UserScripts)
        # -------------------------------------------------------------
        scripts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scripts_box.set_margin_top(14)
        scripts_box.set_margin_bottom(14)
        scripts_box.set_margin_start(16)
        scripts_box.set_margin_end(16)

        scripts_top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_scripts = Gtk.Label(label=f"<b><span size='11500'>{GLib.markup_escape_text(t('userscripts_title'))}</span></b>")
        lbl_scripts.set_use_markup(True)
        lbl_scripts.set_xalign(0.0)
        scripts_top_bar.pack_start(lbl_scripts, True, True, 0)

        btn_add_script = Gtk.Button(label=t('add_new_script'))
        btn_add_script.get_style_context().add_class("btn-primary-glow")
        scripts_top_bar.pack_end(btn_add_script, False, False, 0)
        scripts_box.pack_start(scripts_top_bar, False, False, 0)

        # Scrolled scripts container
        scripts_scroll = Gtk.ScrolledWindow()
        scripts_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scripts_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scripts_scroll.add(scripts_vbox)
        scripts_box.pack_start(scripts_scroll, True, True, 0)

        def populate_scripts():
            for child in scripts_vbox.get_children():
                scripts_vbox.remove(child)

            scripts = self.config.get_user_scripts()
            if not scripts:
                empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                empty_box.get_style_context().add_class("theme-card-box")
                empty_box.set_margin_top(20)
                empty_box.set_margin_bottom(20)

                empty_icon = Gtk.Label(label="🧩")
                empty_icon.get_style_context().add_class("banner-icon")
                empty_box.pack_start(empty_icon, False, False, 0)

                empty_lbl = Gtk.Label(label=t('empty_scripts'))
                empty_lbl.set_justify(Gtk.Justification.CENTER)
                empty_box.pack_start(empty_lbl, True, True, 6)
                scripts_vbox.pack_start(empty_box, True, True, 10)
            else:
                for s in scripts:
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                    row.get_style_context().add_class("item-card-row")

                    sw = Gtk.Switch()
                    sw.set_active(s.get("enabled", True))
                    s_id = s["id"]
                    sw.connect("state-set", lambda widget, state, sid=s_id: self.config.toggle_user_script(sid))
                    row.pack_start(sw, False, False, 4)

                    info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                    title_lbl = Gtk.Label(label=f"<b>{GLib.markup_escape_text(s.get('name', 'Brez imena'))}</b>")
                    title_lbl.set_use_markup(True)
                    title_lbl.set_xalign(0.0)
                    info_box.pack_start(title_lbl, False, False, 0)

                    pattern_txt = f"Domena: <tt>{GLib.markup_escape_text(s.get('pattern', '*'))}</tt> • Zagon: {s.get('run_at', 'end').upper()}"
                    meta_lbl = Gtk.Label(label=pattern_txt)
                    meta_lbl.set_use_markup(True)
                    meta_lbl.set_xalign(0.0)
                    meta_lbl.get_style_context().add_class("text-muted")
                    info_box.pack_start(meta_lbl, False, False, 0)
                    row.pack_start(info_box, True, True, 0)

                    btn_edit = Gtk.Button(label=f"✏️ {t('edit')}")
                    btn_edit.get_style_context().add_class("nav-btn")
                    s_copy = s.copy()
                    btn_edit.connect("clicked", lambda b, script_data=s_copy: [self.open_script_editor_dialog(script_data), populate_scripts()])
                    row.pack_end(btn_edit, False, False, 0)

                    btn_del = Gtk.Button(label="🗑️")
                    btn_del.get_style_context().add_class("btn-delete")
                    btn_del.connect("clicked", lambda b, sid=s_id: [self.config.delete_user_script(sid), populate_scripts()])
                    row.pack_end(btn_del, False, False, 0)

                    scripts_vbox.pack_start(row, False, False, 0)
            scripts_vbox.show_all()

        populate_scripts()
        btn_add_script.connect("clicked", lambda b: [self.open_script_editor_dialog(None), populate_scripts()])

        notebook.append_page(scripts_box, Gtk.Label(label=f"🧩 {t('tab_scripts')}"))

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def open_script_editor_dialog(self, script=None):
        """Urejevalnik uporabniške JavaScript skripte."""
        is_edit = script is not None
        title = "Uredi skripto" if is_edit else "Nova uporabniška skripta"
        dialog = Gtk.Dialog(title=title, transient_for=self, flags=0)
        dialog.set_default_size(680, 520)
        dialog.get_style_context().add_class("customizer-dialog")
        btn_cancel = dialog.add_button(t("cancel", "Prekliči"), Gtk.ResponseType.CANCEL)
        btn_cancel.get_style_context().add_class("customizer-close-btn")
        btn_save = dialog.add_button(f"💾 {t('save')}", Gtk.ResponseType.OK)
        btn_save.get_style_context().add_class("btn-primary-glow")

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_left(16)
        content.set_margin_right(16)

        # Name Entry
        lbl_name = Gtk.Label(label="Ime skripte:")
        lbl_name.set_xalign(0.0)
        content.pack_start(lbl_name, False, False, 0)
        entry_name = Gtk.Entry()
        entry_name.set_text(script.get("name", "") if is_edit else "Moja nova skripta")
        content.pack_start(entry_name, False, False, 0)

        # Match Pattern
        lbl_pat = Gtk.Label(label="Domena ali vzorec URL-ja (* za vse strani, npr. *youtube.com*):")
        lbl_pat.set_xalign(0.0)
        content.pack_start(lbl_pat, False, False, 0)
        entry_pat = Gtk.Entry()
        entry_pat.set_text(script.get("pattern", "*") if is_edit else "*")
        content.pack_start(entry_pat, False, False, 0)

        # Run at
        lbl_run = Gtk.Label(label="Čas zagona skripte:")
        lbl_run.set_xalign(0.0)
        content.pack_start(lbl_run, False, False, 0)
        combo_run = Gtk.ComboBoxText()
        combo_run.append("end", "Ko je stran v celoti naložena (END)")
        combo_run.append("start", "Pred začetkom nalaganja DOM-a (START)")
        combo_run.set_active_id(script.get("run_at", "end") if is_edit else "end")
        content.pack_start(combo_run, False, False, 0)

        # Code View
        lbl_code = Gtk.Label(label="JavaScript koda:")
        lbl_code.set_xalign(0.0)
        content.pack_start(lbl_code, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(180)

        tv = Gtk.TextView()
        tv.get_style_context().add_class("code-editor")
        buf = tv.get_buffer()
        default_code = script.get("code", "") if is_edit else """// Safeer Uporabniška Skripta (Tampermonkey slog)
(function() {
    console.log("Safeer skripta teče na:", window.location.href);
    // Tukaj dodajte svojo JavaScript kodo:
    
})();"""
        buf.set_text(default_code)
        scroll.add(tv)
        content.pack_start(scroll, True, True, 0)

        dialog.show_all()
        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            s_name = entry_name.get_text().strip() or "Brez imena"
            s_pat = entry_pat.get_text().strip() or "*"
            s_run = combo_run.get_active_id() or "end"
            start, end = buf.get_bounds()
            s_code = buf.get_text(start, end, True)

            if is_edit:
                self.config.update_user_script(
                    script["id"],
                    name=s_name,
                    pattern=s_pat,
                    code=s_code,
                    enabled=script.get("enabled", True),
                    run_at=s_run
                )
            else:
                self.config.add_user_script(
                    name=s_name,
                    pattern=s_pat,
                    code=s_code,
                    run_at=s_run
                )
        dialog.destroy()

    def broadcast_portals_update(self):
        """Osveži priljubljene portale na vseh odprtih zavihkih z domačo stranjo."""
        portals = self.config.get_portals()
        portals_json = json.dumps(portals)
        js = f"if (window.setCustomPortals) {{ window.setCustomPortals({portals_json}); }}"
        for t in self.tabs:
            wv = t.get("webview")
            uri = t.get("uri", "")
            if wv and ("home.html" in uri or uri == "safeer://home"):
                wv.run_javascript(js, None, None, None)

    def broadcast_language_update(self):
        """Osveži jezik na vseh odprtih zavihkih z domačo stranjo."""
        lang = get_current_language()
        js = f"if (window.setAppLanguage) {{ window.setAppLanguage('{lang}'); }}"
        for t in self.tabs:
            wv = t.get("webview")
            uri = t.get("uri", "")
            if wv and ("home.html" in uri or uri == "safeer://home"):
                wv.run_javascript(js, None, None, None)

    def broadcast_search_engine_update(self):
        """Osveži privzeti iskalnik na vseh odprtih zavihkih z domačo stranjo."""
        engine = self.config.get("search_engine", "google")
        js = f"if (window.setSearchEngine) {{ window.setSearchEngine('{engine}'); }}"
        for t in self.tabs:
            wv = t.get("webview")
            uri = t.get("uri", "")
            if wv and ("home.html" in uri or uri == "safeer://home"):
                wv.run_javascript(js, None, None, None)

    def open_portal_editor_dialog(self, portal=None, on_saved=None, prefill=None):
        """Dialog za dodajanje ali urejanje priljubljenega portala / strani."""
        is_edit = portal is not None
        title = f"✏️ {t('edit')} {t('tab_portals')}" if is_edit else f"➕ {t('add_portal')}"
        dialog = Gtk.Dialog(title=title, transient_for=self, flags=0)
        dialog.set_default_size(600, 500)
        dialog.set_resizable(True)
        dialog.set_position(Gtk.WindowPosition.CENTER)
        dialog.get_style_context().add_class("customizer-dialog")
        btn_cancel = dialog.add_button(t("cancel", "Prekliči"), Gtk.ResponseType.CANCEL)
        btn_cancel.get_style_context().add_class("customizer-close-btn")
        btn_save = dialog.add_button(f"💾 {t('save_portal')}", Gtk.ResponseType.OK)
        btn_save.get_style_context().add_class("btn-primary-glow")

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(14)
        content.set_margin_bottom(14)
        content.set_margin_start(16)
        content.set_margin_end(16)

        lbl_title = Gtk.Label(label=f"<b>{GLib.markup_escape_text(t('portal_name'))}:</b>")
        lbl_title.set_use_markup(True)
        lbl_title.set_xalign(0.0)
        content.pack_start(lbl_title, False, False, 0)
        entry_title = Gtk.Entry()
        entry_title.set_placeholder_text("YouTube, 24ur, Reddit, GitHub...")
        if is_edit:
            entry_title.set_text(portal.get("title", ""))
        elif prefill and prefill.get("title"):
            entry_title.set_text(prefill.get("title"))
        content.pack_start(entry_title, False, False, 0)

        lbl_url = Gtk.Label(label=f"<b>{GLib.markup_escape_text(t('portal_url'))}:</b>")
        lbl_url.set_use_markup(True)
        lbl_url.set_xalign(0.0)
        content.pack_start(lbl_url, False, False, 0)
        entry_url = Gtk.Entry()
        entry_url.set_placeholder_text("https://...")
        if is_edit:
            entry_url.set_text(portal.get("url", "https://"))
        elif prefill and prefill.get("url"):
            entry_url.set_text(prefill.get("url"))
        else:
            entry_url.set_text("https://")
        content.pack_start(entry_url, False, False, 0)

        lbl_mark = Gtk.Label(label=f"<b>{GLib.markup_escape_text(t('portal_icon'))}:</b>")
        lbl_mark.set_use_markup(True)
        lbl_mark.set_xalign(0.0)
        content.pack_start(lbl_mark, False, False, 0)

        mark_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry_mark = Gtk.Entry()
        entry_mark.set_max_length(4)
        entry_mark.set_width_chars(6)
        entry_mark.set_text(portal.get("mark", "🌐") if is_edit else "⭐")
        mark_box.pack_start(entry_mark, False, False, 0)

        emojis = ["📺", "🎬", "🎵", "📰", "🎮", "🤖", "📊", "💬", "🌐", "⭐", "🚀", "🛒"]
        for em in emojis:
            btn_em = Gtk.Button(label=em)
            btn_em.connect("clicked", lambda b, e=em: entry_mark.set_text(e))
            mark_box.pack_start(btn_em, False, False, 0)
        content.pack_start(mark_box, False, False, 0)

        lbl_color = Gtk.Label(label=f"<b>{GLib.markup_escape_text(t('portal_color'))}:</b>")
        lbl_color.set_use_markup(True)
        lbl_color.set_xalign(0.0)
        content.pack_start(lbl_color, False, False, 0)

        selected_color = [portal.get("color", "#00d2ff") if is_edit else "#10b981"]
        colors_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        color_presets = [
            ("🔴 Rdeča", "#cc0000"),
            ("🔵 Modra", "#0284c7"),
            ("🟢 Mint", "#10b981"),
            ("🟣 Vijolična", "#a855f7"),
            ("🟠 Oranžna", "#f59e0b"),
            ("⚫ Temna", "#1e293b"),
            ("✨ Cian", "#00d2ff")
        ]
        lbl_curr_color = Gtk.Label(label=f"HEX: {selected_color[0]}")
        for cname, chex in color_presets:
            btn_c = Gtk.Button(label=cname)
            def on_c_click(b, hex_code=chex):
                selected_color[0] = hex_code
                lbl_curr_color.set_text(f"HEX: {hex_code}")
            btn_c.connect("clicked", on_c_click)
            colors_box.pack_start(btn_c, False, False, 0)
        content.pack_start(colors_box, False, False, 0)
        content.pack_start(lbl_curr_color, False, False, 0)

        dialog.show_all()
        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            p_title = entry_title.get_text().strip() or "Priljubljena stran"
            p_url = entry_url.get_text().strip() or "https://"
            p_mark = entry_mark.get_text().strip() or "🌐"
            p_color = selected_color[0]
            p_bg = f"linear-gradient(145deg, #091a28, {p_color})"

            if is_edit:
                self.config.update_portal(portal["id"], title=p_title, url=p_url, mark=p_mark, bg=p_bg, color=p_color)
            else:
                self.config.add_portal(title=p_title, url=p_url, mark=p_mark, bg=p_bg, color=p_color)

            self.broadcast_portals_update()
            if on_saved:
                on_saved()

        dialog.destroy()

    def open_portals_dialog(self):
        """Samostojno okno za upravljanje priljubljenih strani in multimedije."""
        dialog = Gtk.Dialog(
            title=f"⭐ {t('portals_title')} — Safeer",
            transient_for=self,
            flags=0
        )
        dialog.set_default_size(840, 600)
        dialog.set_resizable(True)
        dialog.set_position(Gtk.WindowPosition.CENTER)
        dialog.get_style_context().add_class("customizer-dialog")
        btn_close = dialog.add_button(t("close", "Zapri"), Gtk.ResponseType.CLOSE)
        btn_close.get_style_context().add_class("customizer-close-btn")

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(16)
        content.set_margin_end(16)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_head = Gtk.Label(label=f"<b>⭐ {t('portals_title')}</b>")
        lbl_head.set_use_markup(True)
        lbl_head.set_xalign(0.0)
        header_box.pack_start(lbl_head, True, True, 0)

        btn_add = Gtk.Button(label=f"➕ {t('add_portal')}")
        btn_add.get_style_context().add_class("nav-btn")
        header_box.pack_end(btn_add, False, False, 0)

        btn_reset = Gtk.Button(label=f"🔄 {t('reset_default')}")
        btn_reset.get_style_context().add_class("btn-delete")
        header_box.pack_end(btn_reset, False, False, 0)
        content.pack_start(header_box, False, False, 0)

        lbl_sub = Gtk.Label(label=t('portals_sub'))
        lbl_sub.set_xalign(0.0)
        content.pack_start(lbl_sub, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_hexpand(True)
        scroll.set_min_content_height(360)

        list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scroll.add(list_box)
        content.pack_start(scroll, True, True, 0)

        def populate_portals():
            for child in list_box.get_children():
                list_box.remove(child)

            portals = self.config.get_portals()
            for p in portals:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                row.get_style_context().add_class("user-script-row")
                row.set_margin_top(4)
                row.set_margin_bottom(4)

                badge = Gtk.Label(label=p.get("mark", "🌐"))
                badge.set_width_chars(3)
                row.pack_start(badge, False, False, 6)

                info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                lbl_title = Gtk.Label(label=f"<b>{p.get('title', '')}</b>")
                lbl_title.set_use_markup(True)
                lbl_title.set_xalign(0.0)
                lbl_url = Gtk.Label(label=p.get('url', ''))
                lbl_url.set_xalign(0.0)
                lbl_url.get_style_context().add_class("text-muted")
                info_box.pack_start(lbl_title, False, False, 0)
                info_box.pack_start(lbl_url, False, False, 0)
                row.pack_start(info_box, True, True, 0)

                btn_edit = Gtk.Button(label=f"✏️ {t('edit')}")
                btn_edit.get_style_context().add_class("nav-btn")
                btn_edit.connect("clicked", lambda b, prt=p: self.open_portal_editor_dialog(prt, on_saved=populate_portals))
                row.pack_end(btn_edit, False, False, 4)

                btn_del = Gtk.Button(label="🗑️")
                btn_del.get_style_context().add_class("btn-delete")
                def on_delete(b, pid=p.get("id")):
                    self.config.delete_portal(pid)
                    self.broadcast_portals_update()
                    populate_portals()
                btn_del.connect("clicked", on_delete)
                row.pack_end(btn_del, False, False, 0)

                list_box.pack_start(row, False, False, 0)

            list_box.show_all()

        populate_portals()
        btn_add.connect("clicked", lambda b: self.open_portal_editor_dialog(None, on_saved=populate_portals))
        def on_reset(b):
            self.config.reset_portals()
            self.broadcast_portals_update()
            populate_portals()
        btn_reset.connect("clicked", on_reset)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def on_js_message(self, content_mgr, js_result):
        try:
            val = js_result.get_js_value()
            json_str = val.to_json(0)
            data = json.loads(json_str)
            action = data.get("action")
            if action == "navigate":
                url = data.get("url")
                if url:
                    wv = self.get_active_webview()
                    if wv:
                        wv.load_uri(url)
            elif action == "set_language":
                lang = data.get("language", "sl")
                self.config.set("language", lang)
                set_language(lang)
                self.update_ui_language()
            elif action == "open_sidebar":
                service = data.get("service")
                if service == "settings":
                    self.open_settings_dialog()
                elif service == "customizer":
                    self.open_customizer_dialog()
                elif service in ["portals", "edit_portals"]:
                    self.open_portals_dialog()
                elif service == "add_portal":
                    self.open_portal_editor_dialog(None)
                else:
                    self.toggle_sidebar_panel(service)
        except Exception as e:
            print(f"[IPC] Napaka: {e}")

    def update_ui_language(self):
        """Posodobi celotno orodno vrstico, orodne namige, naslove in zavihke ob menjavi jezika."""
        self.set_title(f"{t('app_title')} — Linux Mint Edition")

        if hasattr(self, 'btn_new_tab'):
            self.btn_new_tab.set_tooltip_text(f"{t('new_tab')} (Ctrl + T)")
        if hasattr(self, 'btn_sidebar'):
            self.btn_sidebar.set_tooltip_text(f"{t('sidebar_display')} (F4)")
        if hasattr(self, 'btn_back'):
            self.btn_back.set_tooltip_text(f"{t('back')} (Alt + ←)")
        if hasattr(self, 'btn_forward'):
            self.btn_forward.set_tooltip_text(f"{t('forward')} (Alt + →)")
        if hasattr(self, 'btn_reload'):
            self.btn_reload.set_tooltip_text(f"{t('reload')} (F5 / Ctrl + R)")
        if hasattr(self, 'btn_shield'):
            self.btn_shield.set_tooltip_text(f"{t('app_title')} Cyber Shield: {t('adblock_active')}")
        if hasattr(self, 'url_entry'):
            self.url_entry.set_placeholder_text(t('search_placeholder'))
        if hasattr(self, 'btn_dark_mode'):
            self.btn_dark_mode.set_tooltip_text(f"{t('force_dark_mode')}")
        if hasattr(self, 'btn_downloads'):
            self.btn_downloads.set_tooltip_text(f"{t('downloads')} (Ctrl + J)")
        if hasattr(self, 'btn_history'):
            self.btn_history.set_tooltip_text(f"{t('history')} (Ctrl + H)")
        if hasattr(self, 'btn_customizer'):
            self.btn_customizer.set_tooltip_text(f"{t('customizer_title')}")
        if hasattr(self, 'btn_keyboard'):
            self.btn_keyboard.set_tooltip_text(f"{t('tab_themes')}")
        if hasattr(self, 'btn_reader'):
            self.btn_reader.set_tooltip_text(t('reader_mode'))
        if hasattr(self, 'btn_pip'):
            self.btn_pip.set_tooltip_text(f"{t('pip_video')}")
        if hasattr(self, 'btn_star'):
            self.btn_star.set_tooltip_text(f"{t('bookmark_page')} (Ctrl + D)")
        self.update_star_status()

        if hasattr(self, 'btn_back_drawer'):
            self.btn_back_drawer.set_tooltip_text(f"{t('back')}")
        if hasattr(self, 'btn_reload_drawer'):
            self.btn_reload_drawer.set_tooltip_text(f"{t('reload')}")
        if hasattr(self, 'btn_popout'):
            self.btn_popout.set_tooltip_text(t('open_file'))
        if hasattr(self, 'btn_close_drawer'):
            self.btn_close_drawer.set_tooltip_text(t('close'))

        self.update_tab_titles_for_language()
        self.broadcast_language_update()

    def update_tab_titles_for_language(self):
        """Posodobi naslove zavihkov in okna v skladu z novim jezikom."""
        for t_info in self.tabs:
            uri = t_info.get("uri", "")
            if "ui/home.html" in uri or uri == "safeer://home":
                h_title = t("home_title")
                t_info["title"] = h_title
                if "title_label" in t_info and t_info["title_label"]:
                    t_info["title_label"].set_text(h_title)
        self.set_title(f"{t('app_title')} — Linux Mint Edition")


def main():
    target_url = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        target_url = sys.argv[1]

    # Preveri, če Safeer že teče – v tem primeru povezavo nemudoma pošlji obstoječi instanci
    sock_path = os.path.join(os.path.expanduser("~/.config/safeer-mint"), "safeer.sock")
    if os.path.exists(sock_path):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1.5)
            s.connect(sock_path)
            cmd = f"OPEN {target_url}" if target_url else "FOCUS"
            s.sendall(cmd.encode("utf-8"))
            s.recv(1024)
            s.close()
            sys.exit(0)
        except Exception:
            try:
                os.remove(sock_path)
            except Exception:
                pass

    app = SafeerMintBrowser(initial_url=target_url)
    app.connect("destroy", Gtk.main_quit)

    # Clean atomic show
    app.show_all()

    if not app.config.get("sidebar_enabled", True):
        app.sidebar_box.hide()
        app.content_paned.set_position(0)
    else:
        app.content_paned.set_position(DOCK_WIDTH)

    Gtk.main()


if __name__ == "__main__":
    main()
