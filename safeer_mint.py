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

from core.config import ConfigManager
from core.adblock import (
    YOUTUBE_ADBLOCK_SCRIPT,
    GENERIC_COSMETIC_SCRIPT,
    is_threat_domain,
    FORCE_DARK_MODE_CSS
)

# Native WebKitGTK user agent matching Safari/WebKit engine to prevent Google CAPTCHA bot triggers
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
DOCK_WIDTH = 54


class SafeerMintBrowser(Gtk.Window):
    def __init__(self, initial_url=None):
        super().__init__(title="Safeer Browser — Linux Mint Edition")
        self.config = ConfigManager()

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

        # Configure Persistent Cookie, LocalStorage & IndexedDB Storage
        self.setup_persistent_storage()
        self.setup_downloads_handling()

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
        """Zapomni si velikost okna ob zaprtju za gladek ponovni zagon."""
        try:
            w, h = self.get_size()
            if w >= 800 and h >= 600:
                self.config.set("window_width", w)
                self.config.set("window_height", h)
        except Exception:
            pass
        return False

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

        # F4 toggles sidebar
        if event.keyval == Gdk.KEY_F4:
            self.toggle_sidebar_visibility()
            return True
        elif ctrl and event.keyval in (Gdk.KEY_t, Gdk.KEY_T):
            self.new_tab()
            return True
        elif ctrl and event.keyval in (Gdk.KEY_w, Gdk.KEY_W):
            if self.active_tab_id:
                self.close_tab(self.active_tab_id)
            return True
        elif ctrl and event.keyval in (Gdk.KEY_h, Gdk.KEY_H):
            self.open_history_dialog()
            return True
        elif ctrl and event.keyval in (Gdk.KEY_j, Gdk.KEY_J):
            self.open_downloads_dialog()
            return True
        elif ctrl and event.keyval in (Gdk.KEY_d, Gdk.KEY_D):
            self.toggle_dark_mode()
            return True
        elif ctrl and event.keyval in (Gdk.KEY_r, Gdk.KEY_R) or event.keyval == Gdk.KEY_F5:
            wv = self.get_active_webview()
            if wv:
                wv.reload()
            return True
        elif alt and event.keyval == Gdk.KEY_Left:
            wv = self.get_active_webview()
            if wv:
                wv.go_back()
            return True
        elif alt and event.keyval == Gdk.KEY_Right:
            wv = self.get_active_webview()
            if wv:
                wv.go_forward()
            return True
        return False

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
        self.btn_new_tab.set_tooltip_text("Odpri nov zavihek (Ctrl + T)")
        self.btn_new_tab.connect("clicked", lambda b: self.new_tab())
        self.tab_bar.pack_start(self.btn_new_tab, False, False, 0)

        self.top_bar.pack_start(self.tab_bar, False, False, 0)

        # 2. Tier 2: Firefox Navigation Bar
        self.nav_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.nav_bar.get_style_context().add_class("nav-toolbar")

        # Sidebar button (▤)
        self.btn_sidebar = Gtk.Button(label="▤")
        self.btn_sidebar.get_style_context().add_class("ff-nav-btn")
        self.btn_sidebar.set_tooltip_text("Stranska orodna vrstica (F4)")
        self.btn_sidebar.connect("clicked", lambda b: self.toggle_sidebar_visibility())
        self.nav_bar.pack_start(self.btn_sidebar, False, False, 0)

        # Back (←)
        self.btn_back = Gtk.Button(label="←")
        self.btn_back.get_style_context().add_class("ff-nav-btn")
        self.btn_back.set_tooltip_text("Nazaj (Alt + Levo)")
        self.btn_back.connect("clicked", lambda b: self.get_active_webview() and self.get_active_webview().go_back())
        self.nav_bar.pack_start(self.btn_back, False, False, 0)

        # Forward (→)
        self.btn_forward = Gtk.Button(label="→")
        self.btn_forward.get_style_context().add_class("ff-nav-btn")
        self.btn_forward.set_tooltip_text("Naprej (Alt + Desno)")
        self.btn_forward.connect("clicked", lambda b: self.get_active_webview() and self.get_active_webview().go_forward())
        self.nav_bar.pack_start(self.btn_forward, False, False, 0)

        # Reload (↻)
        self.btn_reload = Gtk.Button(label="↻")
        self.btn_reload.get_style_context().add_class("ff-nav-btn")
        self.btn_reload.set_tooltip_text("Osveži stran (F5 / Ctrl + R)")
        self.btn_reload.connect("clicked", lambda b: self.get_active_webview() and self.get_active_webview().reload())
        self.nav_bar.pack_start(self.btn_reload, False, False, 0)

        # 3. Firefox Awesomebar / URL Box
        self.url_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.url_box.get_style_context().add_class("ff-url-container")

        # Tracking protection shield inside URL bar
        self.btn_shield = Gtk.Button(label="🛡️")
        self.btn_shield.get_style_context().add_class("ff-shield-btn")
        self.btn_shield.set_tooltip_text("Safeer Cyber Shield: Aktivna zaščita pred sledilci in oglasom")
        self.btn_shield.connect("clicked", lambda b: self.show_shield_status_dialog())
        self.url_box.pack_start(self.btn_shield, False, False, 0)

        # Security tune sliders icon
        self.security_icon = Gtk.Label(label="🎚️")
        self.security_icon.get_style_context().add_class("ff-security-icon")
        self.url_box.pack_start(self.security_icon, False, False, 0)

        # Clean URL Entry with large Ubuntu font
        self.url_entry = Gtk.Entry()
        self.url_entry.get_style_context().add_class("ff-url-entry")
        self.url_entry.set_placeholder_text("Iščite ali vnesite naslov spletnega mesta...")
        self.url_entry.connect("activate", self.on_url_activate)
        self.url_entry.connect("focus-in-event", self.on_url_focus_in)
        self.url_entry.connect("focus-out-event", self.on_url_focus_out)
        self.url_box.pack_start(self.url_entry, True, True, 0)

        self.nav_bar.pack_start(self.url_box, True, True, 4)

        # Force Dark Mode Toggle Button (🌙 / ☀️)
        is_dark = self.config.get("force_dark_mode", False)
        self.btn_dark_mode = Gtk.Button(label="🌙" if is_dark else "☀️")
        self.btn_dark_mode.get_style_context().add_class("ff-nav-btn")
        if is_dark:
            self.btn_dark_mode.get_style_context().add_class("active")
        self.btn_dark_mode.set_tooltip_text("Prisili temni način (Force Dark Mode) — " + ("Vklopljen" if is_dark else "Izklopljen"))
        self.btn_dark_mode.connect("clicked", self.toggle_dark_mode)
        self.nav_bar.pack_start(self.btn_dark_mode, False, False, 0)

        # Downloads Button (📥)
        self.btn_downloads = Gtk.Button(label="📥")
        self.btn_downloads.get_style_context().add_class("ff-nav-btn")
        self.btn_downloads.set_tooltip_text("Prenosi datotek (Ctrl + J)")
        self.btn_downloads.connect("clicked", lambda b: self.open_downloads_dialog())
        self.nav_bar.pack_start(self.btn_downloads, False, False, 0)

        # History Button (🕒)
        self.btn_history = Gtk.Button(label="🕒")
        self.btn_history.get_style_context().add_class("ff-nav-btn")
        self.btn_history.set_tooltip_text("Zgodovina brskanja (Ctrl + H)")
        self.btn_history.connect("clicked", lambda b: self.open_history_dialog())
        self.nav_bar.pack_start(self.btn_history, False, False, 0)

        # Customizer & Scripts Button (🧩)
        self.btn_customizer = Gtk.Button(label="🧩")
        self.btn_customizer.get_style_context().add_class("ff-nav-btn")
        self.btn_customizer.set_tooltip_text("Prilagoditev videza & Uporabniške skripte (Tampermonkey)")
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
            decision.use()
            return True
        return False

    def open_add_page_dialog(self):
        """Dialog za hitro dodajanje nove strani v stransko orodno vrstico."""
        dialog = Gtk.Dialog(
            title="Dodaj stran v stransko vrstico",
            transient_for=self,
            flags=0
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            "Dodaj", Gtk.ResponseType.OK
        )
        dialog.set_default_size(380, 240)

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
            title="Nastavitve Safeer Browser",
            transient_for=self,
            flags=0
        )
        dialog.add_buttons("Zapri", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(500, 500)

        box = dialog.get_content_area()
        box.set_spacing(12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # 1. Permanent Sidebar Toggle
        title_sidebar = Gtk.Label(label="<b>Prikaz stranske vrstice:</b>")
        title_sidebar.set_use_markup(True)
        title_sidebar.set_halign(Gtk.Align.START)
        box.pack_start(title_sidebar, False, False, 0)

        sb_check = Gtk.CheckButton(label="Prikaži stransko vrstico (Trajno ob zagonu)")
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
        title_items = Gtk.Label(label="<b>Stranske strani (Vklop / Izbris):</b>")
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

        if text == "safeer://home" or text == "about:blank":
            self.load_homepage()
            return

        if is_threat_domain(text):
            self.show_threat_warning(text)
            return

        if not text.startswith("http://") and not text.startswith("https://"):
            if "." in text and " " not in text:
                target = "https://" + text
            else:
                target = f"https://www.google.com/search?q={urllib.parse.quote_plus(text)}"
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

        btn_close = Gtk.Button(label="✕")
        btn_close.get_style_context().add_class("tab-close-btn")
        btn_close.set_tooltip_text("Zapri zavihek (Ctrl + W)")
        btn_close.connect("clicked", lambda b: self.close_tab(tab_id))
        tab_box.pack_start(btn_close, False, False, 2)

        tab_event_box = Gtk.EventBox()
        tab_event_box.add(tab_box)
        tab_event_box.connect("button-press-event", lambda w, ev: self.switch_to_tab(tab_id))

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

    def on_tab_load_changed(self, tab_id, webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            uri = webview.get_uri() or ""
            title = webview.get_title() or ""

            for t in self.tabs:
                if t["id"] == tab_id:
                    t["uri"] = uri
                    if "ui/home.html" in uri:
                        t["title"] = "Safeer Domača Stran"
                        t["icon"] = "🍃"
                        t["title_label"].set_text("Safeer Domača Stran")
                        t["icon_label"].set_text("🍃")
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
        dialog = Gtk.Dialog(title="📥 Prenosi — Safeer Browser", transient_for=self, flags=0)
        dialog.set_default_size(540, 420)
        dialog.add_button("Zapri", Gtk.ResponseType.CLOSE)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_left(16)
        content.set_margin_right(16)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_title = Gtk.Label(label="<b>Aktivni in nedavni prenosi</b>")
        lbl_title.set_use_markup(True)
        lbl_title.set_xalign(0.0)
        header_box.pack_start(lbl_title, True, True, 0)

        btn_open_folder = Gtk.Button(label="📁 Odpri mapo Prenosi")
        btn_open_folder.get_style_context().add_class("nav-btn")
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
            empty_lbl = Gtk.Label(label="Ni nedavnih prenosov.")
            empty_lbl.get_style_context().add_class("tab-title")
            dls_vbox.pack_start(empty_lbl, True, True, 20)
        else:
            for dl in self.downloads:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                row.get_style_context().add_class("drawer-header-bar")

                icon_lbl = Gtk.Label(label="✅" if dl["status"] == "completed" else ("⬇️" if dl["status"] == "running" else "❌"))
                row.pack_start(icon_lbl, False, False, 4)

                meta_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                fname_lbl = Gtk.Label(label=f"<b>{dl['filename']}</b>")
                fname_lbl.set_use_markup(True)
                fname_lbl.set_xalign(0.0)
                fname_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                meta_box.pack_start(fname_lbl, False, False, 0)

                status_txt = f"{dl['time']} • " + ("Končano" if dl["status"] == "completed" else (f"Prenašam... {int(dl['progress']*100)}%" if dl["status"] == "running" else "Napaka"))
                status_lbl = Gtk.Label(label=status_txt)
                status_lbl.set_xalign(0.0)
                status_lbl.get_style_context().add_class("tab-title")
                meta_box.pack_start(status_lbl, False, False, 0)
                row.pack_start(meta_box, True, True, 0)

                if dl["status"] == "completed" and os.path.exists(dl["path"]):
                    btn_open = Gtk.Button(label="Odpri")
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
        dialog = Gtk.Dialog(title="🕒 Zgodovina brskanja — Safeer Browser", transient_for=self, flags=0)
        dialog.set_default_size(680, 480)
        dialog.add_button("Zapri", Gtk.ResponseType.CLOSE)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_left(16)
        content.set_margin_right(16)

        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search_entry = Gtk.Entry()
        search_entry.set_placeholder_text("🔍 Išči po zgodovini obiskov...")
        search_entry.get_style_context().add_class("ff-url-entry")
        top_box.pack_start(search_entry, True, True, 0)

        btn_clear = Gtk.Button(label="🗑️ Počisti zgodovino")
        btn_clear.get_style_context().add_class("btn-delete")
        top_box.pack_start(btn_clear, False, False, 0)

        btn_clear_cookies = Gtk.Button(label="🍪 Piškotki & Podatki")
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

        col_time = Gtk.TreeViewColumn("Čas", Gtk.CellRendererText(), text=0)
        col_time.set_min_width(130)
        tree.append_column(col_time)

        col_title = Gtk.TreeViewColumn("Naslov", Gtk.CellRendererText(), text=1)
        col_title.set_min_width(220)
        tree.append_column(col_title)

        col_url = Gtk.TreeViewColumn("URL", Gtk.CellRendererText(), text=2)
        col_url.set_min_width(260)
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
            title="🧹 Počisti podatke brskanja — Safeer Browser",
            transient_for=self,
            flags=0
        )
        dialog.set_default_size(460, 320)
        dialog.add_button("Prekliči", Gtk.ResponseType.CANCEL)
        btn_confirm = dialog.add_button("Počisti izbrano", Gtk.ResponseType.OK)
        btn_confirm.get_style_context().add_class("btn-delete")

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_left(20)
        content.set_margin_right(20)

        header = Gtk.Label(label="<b>Izberite podatke, ki jih želite odstraniti:</b>")
        header.set_use_markup(True)
        header.set_xalign(0.0)
        content.pack_start(header, False, False, 0)

        check_history = Gtk.CheckButton(label="🕒 Zgodovina brskanja (seznam vseh obiskanih strani)")
        check_history.set_active(True)
        content.pack_start(check_history, False, False, 2)

        check_cookies = Gtk.CheckButton(label="🍪 Piškotki in prijavne seje (odjavi vas z vseh strani)")
        check_cookies.set_active(True)
        content.pack_start(check_cookies, False, False, 2)

        check_cache = Gtk.CheckButton(label="💾 Predpomnilnik in shramba spletnih mest (sprosti disk)")
        check_cache.set_active(True)
        content.pack_start(check_cache, False, False, 2)

        dialog.show_all()
        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            do_hist = check_history.get_active()
            do_cookies = check_cookies.get_active()
            do_cache = check_cache.get_active()
            dialog.destroy()

            msg_parts = []
            if do_hist:
                self.save_history([])
                msg_parts.append("Zgodovina")

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
                msg_parts.append("Piškotki")

            if do_cache:
                types_to_clear |= WebKit2.WebsiteDataTypes.DISK_CACHE
                types_to_clear |= WebKit2.WebsiteDataTypes.MEMORY_CACHE
                types_to_clear |= WebKit2.WebsiteDataTypes.DOM_CACHE
                types_to_clear |= WebKit2.WebsiteDataTypes.INDEXEDDB_DATABASES
                types_to_clear |= WebKit2.WebsiteDataTypes.WEBSQL_DATABASES
                types_to_clear |= WebKit2.WebsiteDataTypes.OFFLINE_APPLICATION_CACHE
                msg_parts.append("Predpomnilnik")

            if types_to_clear != 0:
                try:
                    self.website_data_manager.clear(types_to_clear, 0, None, None, None)
                except Exception as e:
                    print(f"[Privacy] Napaka pri brisanju podatkov: {e}")

            info_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="✅ Podatki brskanja uspešno očiščeni!"
            )
            info_dialog.format_secondary_text(
                f"Uspešno odstranjeno: {', '.join(msg_parts)}.\n"
                "Vaša zasebnost je zaščitena."
            )
            info_dialog.run()
            info_dialog.destroy()
        else:
            dialog.destroy()

    def open_customizer_dialog(self):
        """Dialog za prilagoditev teme, lastnega CSS-ja in uporabniških skript (Tampermonkey)."""
        dialog = Gtk.Dialog(
            title="🧩 Prilagoditev brskalnika & Uporabniške skripte — Safeer",
            transient_for=self,
            flags=0
        )
        dialog.set_default_size(720, 520)
        dialog.add_button("Zapri", Gtk.ResponseType.CLOSE)

        content = dialog.get_content_area()
        content.set_spacing(6)
        content.set_margin_top(8)
        content.set_margin_bottom(8)
        content.set_margin_left(12)
        content.set_margin_right(12)

        notebook = Gtk.Notebook()
        content.pack_start(notebook, True, True, 0)

        # -------------------------------------------------------------
        # ZAVIHEK 1: 🎨 Teme & Videz
        # -------------------------------------------------------------
        themes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        themes_box.set_margin_top(12)
        themes_box.set_margin_bottom(12)
        themes_box.set_margin_left(12)
        themes_box.set_margin_right(12)

        lbl_theme = Gtk.Label(label="<b>Izbira barvne teme brskalnika:</b>")
        lbl_theme.set_use_markup(True)
        lbl_theme.set_xalign(0.0)
        themes_box.pack_start(lbl_theme, False, False, 0)

        # Theme Radio Buttons
        cur_theme = self.config.get("theme", "midnight")
        radio_midnight = Gtk.RadioButton.new_with_label(None, "🌙 Firefox Midnight (Eleganten temen videz)")
        radio_mint = Gtk.RadioButton.new_with_label_from_widget(radio_midnight, "🍃 Linux Mint Emerald (Zeleni poudarki)")
        radio_neon = Gtk.RadioButton.new_with_label_from_widget(radio_midnight, "⚡ Cyberpunk Neon (Cian & Vijolična)")
        radio_amoled = Gtk.RadioButton.new_with_label_from_widget(radio_midnight, "🖤 Pure AMOLED Black (Globoka črna)")

        if cur_theme == "mint":
            radio_mint.set_active(True)
        elif cur_theme == "neon":
            radio_neon.set_active(True)
        elif cur_theme == "amoled":
            radio_amoled.set_active(True)
        else:
            radio_midnight.set_active(True)

        def on_theme_changed(btn, theme_name):
            if btn.get_active():
                self.config.set("theme", theme_name)
                self.apply_css()

        radio_midnight.connect("toggled", on_theme_changed, "midnight")
        radio_mint.connect("toggled", on_theme_changed, "mint")
        radio_neon.connect("toggled", on_theme_changed, "neon")
        radio_amoled.connect("toggled", on_theme_changed, "amoled")

        themes_box.pack_start(radio_midnight, False, False, 2)
        themes_box.pack_start(radio_mint, False, False, 2)
        themes_box.pack_start(radio_neon, False, False, 2)
        themes_box.pack_start(radio_amoled, False, False, 2)

        sep_css = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        themes_box.pack_start(sep_css, False, False, 6)

        lbl_css = Gtk.Label(label="<b>Lasten CSS slog (userChrome.css za napredne uporabnike):</b>")
        lbl_css.set_use_markup(True)
        lbl_css.set_xalign(0.0)
        themes_box.pack_start(lbl_css, False, False, 0)

        css_scroll = Gtk.ScrolledWindow()
        css_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        css_scroll.set_min_content_height(140)

        css_tv = Gtk.TextView()
        css_tv.get_style_context().add_class("code-editor")
        css_buf = css_tv.get_buffer()
        css_buf.set_text(self.config.get("custom_css", ""))
        css_scroll.add(css_tv)
        themes_box.pack_start(css_scroll, True, True, 0)

        btn_apply_css = Gtk.Button(label="💾 Shrani in uveljavi lasten CSS")
        btn_apply_css.get_style_context().add_class("nav-btn")
        def on_save_css(b):
            start, end = css_buf.get_bounds()
            custom_code = css_buf.get_text(start, end, True)
            self.config.set("custom_css", custom_code)
            self.apply_css()
        btn_apply_css.connect("clicked", on_save_css)
        themes_box.pack_start(btn_apply_css, False, False, 0)

        notebook.append_page(themes_box, Gtk.Label(label="🎨 Teme & Lasten CSS"))

        # -------------------------------------------------------------
        # ZAVIHEK 2: 🧩 Uporabniške skripte (UserScripts)
        # -------------------------------------------------------------
        scripts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        scripts_box.set_margin_top(12)
        scripts_box.set_margin_bottom(12)
        scripts_box.set_margin_left(12)
        scripts_box.set_margin_right(12)

        scripts_top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_scripts = Gtk.Label(label="<b>Nameščene uporabniške skripte (Tampermonkey slog):</b>")
        lbl_scripts.set_use_markup(True)
        lbl_scripts.set_xalign(0.0)
        scripts_top_bar.pack_start(lbl_scripts, True, True, 0)

        btn_add_script = Gtk.Button(label="➕ Dodaj novo skripto")
        btn_add_script.get_style_context().add_class("nav-btn")
        scripts_top_bar.pack_start(btn_add_script, False, False, 0)
        scripts_box.pack_start(scripts_top_bar, False, False, 0)

        # Scrolled scripts container
        scripts_scroll = Gtk.ScrolledWindow()
        scripts_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scripts_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scripts_scroll.add(scripts_vbox)
        scripts_box.pack_start(scripts_scroll, True, True, 0)

        def populate_scripts():
            for child in scripts_vbox.get_children():
                scripts_vbox.remove(child)

            scripts = self.config.get_user_scripts()
            if not scripts:
                empty_lbl = Gtk.Label(label="Trenutno nimate dodanih lastnih skript.\nKliknite 'Dodaj novo skripto' za ustvarjanje prve JavaScript razširitve!")
                empty_lbl.get_style_context().add_class("tab-title")
                scripts_vbox.pack_start(empty_lbl, True, True, 30)
            else:
                for s in scripts:
                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                    row.get_style_context().add_class("drawer-header-bar")

                    # Enable Switch
                    sw = Gtk.Switch()
                    sw.set_active(s.get("enabled", True))
                    s_id = s["id"]
                    sw.connect("state-set", lambda widget, state, sid=s_id: self.config.toggle_user_script(sid))
                    row.pack_start(sw, False, False, 4)

                    # Info
                    info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                    title_lbl = Gtk.Label(label=f"<b>{s.get('name', 'Brez imena')}</b>")
                    title_lbl.set_use_markup(True)
                    title_lbl.set_xalign(0.0)
                    info_box.pack_start(title_lbl, False, False, 0)

                    pattern_txt = f"Domena: <code>{s.get('pattern', '*')}</code> • Zagon: {s.get('run_at', 'end').upper()}"
                    meta_lbl = Gtk.Label(label=pattern_txt)
                    meta_lbl.set_use_markup(True)
                    meta_lbl.set_xalign(0.0)
                    meta_lbl.get_style_context().add_class("tab-title")
                    info_box.pack_start(meta_lbl, False, False, 0)
                    row.pack_start(info_box, True, True, 0)

                    # Edit button
                    btn_edit = Gtk.Button(label="✏️ Uredi")
                    btn_edit.get_style_context().add_class("nav-btn")
                    s_copy = s.copy()
                    btn_edit.connect("clicked", lambda b, script_data=s_copy: [self.open_script_editor_dialog(script_data), populate_scripts()])
                    row.pack_end(btn_edit, False, False, 0)

                    # Delete button
                    btn_del = Gtk.Button(label="🗑️")
                    btn_del.get_style_context().add_class("btn-delete")
                    btn_del.connect("clicked", lambda b, sid=s_id: [self.config.delete_user_script(sid), populate_scripts()])
                    row.pack_end(btn_del, False, False, 0)

                    scripts_vbox.pack_start(row, False, False, 0)
            scripts_vbox.show_all()

        populate_scripts()
        btn_add_script.connect("clicked", lambda b: [self.open_script_editor_dialog(None), populate_scripts()])

        notebook.append_page(scripts_box, Gtk.Label(label="🧩 Uporabniške skripte (UserScripts)"))

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def open_script_editor_dialog(self, script=None):
        """Urejevalnik uporabniške JavaScript skripte."""
        is_edit = script is not None
        title = "Uredi skripto" if is_edit else "Nova uporabniška skripta"
        dialog = Gtk.Dialog(title=title, transient_for=self, flags=0)
        dialog.set_default_size(600, 480)
        dialog.add_button("Prekliči", Gtk.ResponseType.CANCEL)
        btn_save = dialog.add_button("💾 Shrani skripto", Gtk.ResponseType.OK)
        btn_save.get_style_context().add_class("nav-btn")

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
            elif action == "open_sidebar":
                service = data.get("service")
                if service == "settings":
                    self.open_settings_dialog()
                elif service == "customizer":
                    self.open_customizer_dialog()
                else:
                    self.toggle_sidebar_panel(service)
        except Exception as e:
            print(f"[IPC] Napaka: {e}")


def main():
    target_url = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        target_url = sys.argv[1]

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
