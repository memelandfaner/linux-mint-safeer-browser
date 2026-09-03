#!/usr/bin/env python3
"""
Safeer Browser — Linux Mint Edition
Desktop-optimized browser with Modular Sidebar (Messenger, Gmail, Custom sites),
YouTube Zero-Ad & Background Audio engine, Cyber Threat Shield, and Persistent Sessions.
"""

import os
import sys
import json
import urllib.parse
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, Gdk, WebKit2, GLib, Gio

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
    is_threat_domain
)

# Native WebKitGTK user agent matching Safari/WebKit engine to prevent Google CAPTCHA bot triggers
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
DOCK_WIDTH = 54


class SafeerMintBrowser(Gtk.Window):
    def __init__(self):
        super().__init__(title="Safeer Browser — Linux Mint Edition")
        self.set_default_size(1280, 820)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Set WM_CLASS so Linux Mint panel associates the window with safeer-browser.desktop
        self.set_wmclass("safeer-browser", "Safeer-browser")

        # Set official window & taskbar icon
        icon_path = os.path.join(BASE_DIR, "assets", "icon.png")
        if os.path.exists(icon_path):
            try:
                self.set_icon_from_file(icon_path)
                Gtk.Window.set_default_icon_from_file(icon_path)
            except Exception as e:
                print(f"[Icon] Opozorilo pri nalaganju ikone: {e}")

        self.config = ConfigManager()
        self.active_sidebar_service = None
        self.dock_buttons = {}

        # Configure Persistent Cookie, LocalStorage & IndexedDB Storage
        self.setup_persistent_storage()

        # Apply Linux Mint Dark Theme preference
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        self.setup_ui()
        self.apply_css()

        # Connect F4 keyboard shortcut to toggle sidebar
        self.connect("key-press-event", self.on_global_key_press)

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

    def setup_ui(self):
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

        # Load initial start page
        self.load_homepage()

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        css_data = """
        window {
            background-color: #080c16;
        }
        .top-toolbar {
            background: linear-gradient(180deg, #0f172a 0%, #090d1a 100%);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding: 8px 14px;
        }
        .mint-badge {
            color: #87cf3e;
            font-weight: 800;
            font-size: 13px;
            padding: 4px 10px;
            border-radius: 8px;
            background: rgba(135, 207, 62, 0.12);
            border: 1px solid rgba(135, 207, 62, 0.25);
            margin-right: 6px;
        }
        .nav-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 9px;
            color: #cbd5e1;
            padding: 6px 13px;
            margin-right: 4px;
            font-size: 13px;
            font-weight: 600;
            transition: all 180ms ease-in-out;
        }
        .nav-btn:hover {
            background: rgba(135, 207, 62, 0.18);
            border-color: #87cf3e;
            color: #ffffff;
            box-shadow: 0 0 10px rgba(135, 207, 62, 0.2);
        }
        .nav-btn.active {
            background: rgba(135, 207, 62, 0.25);
            border-color: #87cf3e;
            color: #87cf3e;
        }
        .nav-btn-shield {
            background: rgba(0, 210, 255, 0.1);
            border: 1px solid rgba(0, 210, 255, 0.3);
            color: #00d2ff;
        }
        .nav-btn-shield:hover {
            background: rgba(0, 210, 255, 0.2);
            border-color: #00d2ff;
            box-shadow: 0 0 12px rgba(0, 210, 255, 0.35);
        }
        .url-entry {
            background: #050811;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 999px;
            color: #ffffff;
            padding: 7px 18px;
            font-size: 13.5px;
            transition: all 180ms ease-in-out;
        }
        .url-entry:focus {
            border-color: #87cf3e;
            box-shadow: 0 0 12px rgba(135, 207, 62, 0.3);
        }
        .dock-bar {
            background-color: #070a14;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            padding: 8px 4px;
            min-width: 52px;
        }
        .dock-btn {
            background: transparent;
            border: none;
            border-left: 3px solid transparent;
            border-radius: 10px;
            padding: 10px 8px;
            margin: 3px 2px;
            color: #94a3b8;
            font-size: 20px;
            transition: all 150ms ease;
        }
        .dock-btn:hover {
            background: rgba(255, 255, 255, 0.08);
            color: #ffffff;
        }
        .dock-btn.active {
            background: rgba(135, 207, 62, 0.18);
            border-left: 3px solid #87cf3e;
            color: #87cf3e;
            box-shadow: 0 0 12px rgba(135, 207, 62, 0.25);
        }
        .drawer-box {
            background-color: #0a0f1d;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }
        .drawer-header-bar {
            background: #0d1527;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding: 8px 12px;
        }
        .btn-delete {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #ef4444;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 600;
        }
        .btn-delete:hover {
            background: #ef4444;
            color: #ffffff;
        }
        """
        css_provider.load_from_data(css_data.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_global_key_press(self, widget, event):
        # F4 toggles sidebar temporarily
        if event.keyval == Gdk.KEY_F4:
            self.toggle_sidebar_visibility()
            return True
        return False

    def create_top_bar(self):
        self.top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.top_bar.get_style_context().add_class("top-toolbar")

        # Linux Mint Brand Badge
        self.mint_badge = Gtk.Label(label="🍃 Safeer Mint")
        self.mint_badge.get_style_context().add_class("mint-badge")
        self.top_bar.pack_start(self.mint_badge, False, False, 2)

        # Back
        self.btn_back = Gtk.Button(label="◀")
        self.btn_back.set_tooltip_text("Nazaj (Alt + Levo)")
        self.btn_back.get_style_context().add_class("nav-btn")
        self.btn_back.connect("clicked", lambda b: self.webview.go_back())
        self.top_bar.pack_start(self.btn_back, False, False, 0)

        # Forward
        self.btn_forward = Gtk.Button(label="▶")
        self.btn_forward.set_tooltip_text("Naprej (Alt + Desno)")
        self.btn_forward.get_style_context().add_class("nav-btn")
        self.btn_forward.connect("clicked", lambda b: self.webview.go_forward())
        self.top_bar.pack_start(self.btn_forward, False, False, 0)

        # Reload
        self.btn_reload = Gtk.Button(label="⟳")
        self.btn_reload.set_tooltip_text("Osveži stran (F5 / Ctrl + R)")
        self.btn_reload.get_style_context().add_class("nav-btn")
        self.btn_reload.connect("clicked", lambda b: self.webview.reload())
        self.top_bar.pack_start(self.btn_reload, False, False, 0)

        # Home
        self.btn_home = Gtk.Button(label="🏠")
        self.btn_home.set_tooltip_text("Domača stran Safeer")
        self.btn_home.get_style_context().add_class("nav-btn")
        self.btn_home.connect("clicked", lambda b: self.load_homepage())
        self.top_bar.pack_start(self.btn_home, False, False, 0)

        # Omnibox / URL Entry
        self.url_entry = Gtk.Entry()
        self.url_entry.get_style_context().add_class("url-entry")
        self.url_entry.set_placeholder_text("Vnesite naslov spletnega mesta ali iskanje...")
        self.url_entry.connect("activate", self.on_url_activate)
        self.top_bar.pack_start(self.url_entry, True, True, 4)

        # Shield Status indicator & Dialog Trigger
        self.btn_shield = Gtk.Button(label="🛡️ Ščit Aktiven")
        self.btn_shield.get_style_context().add_class("nav-btn")
        self.btn_shield.get_style_context().add_class("nav-btn-shield")
        self.btn_shield.set_tooltip_text("Safeer Shield: Blokiranje oglasov, YouTube zaščita & abuse.ch C2 Ščit")
        self.btn_shield.connect("clicked", lambda b: self.show_shield_status_dialog())
        self.top_bar.pack_start(self.btn_shield, False, False, 2)

        # Toggle Sidebar Button (Začasno skrij/pokaži)
        self.btn_sidebar = Gtk.Button(label="▤ Stranska vrstica")
        self.btn_sidebar.get_style_context().add_class("nav-btn")
        self.btn_sidebar.set_tooltip_text("Začasno skrij ali pokaži stransko vrstico (Bližnjica: F4)")
        self.btn_sidebar.connect("clicked", lambda b: self.toggle_sidebar_visibility())
        self.top_bar.pack_start(self.btn_sidebar, False, False, 0)

        # Optional Virtual Keyboard Toggle Button (Default OFF)
        self.btn_keyboard = Gtk.Button(label="⌨️ Tipkovnica")
        self.btn_keyboard.get_style_context().add_class("nav-btn")
        self.btn_keyboard.set_tooltip_text("Vklopi/izklopi navidezno tipkovnico na zaslonu")
        self.btn_keyboard.connect("clicked", self.toggle_virtual_keyboard)
        self.top_bar.pack_start(self.btn_keyboard, False, False, 0)

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
                self.sidebar_drawer.show_all()
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
            self.webview.load_uri(uri)
            self.close_sidebar_panel()

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

            # Show drawer and expand divider
            self.sidebar_drawer.show_all()
            drawer_w = self.config.get("sidebar_width", 420)
            if drawer_w > 650 or drawer_w < 300:
                drawer_w = 420
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
            if 300 <= drawer_w <= 650:
                self.config.set("sidebar_width", drawer_w)

    def on_create_webview(self, webview, action):
        """Preusmeri nova okna/povezave v glavno okno brskalnika."""
        nav_action = action.get_navigation_action()
        request = nav_action.get_request()
        uri = request.get_uri()
        if uri:
            self.webview.load_uri(uri)
        return None

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

        # 4. Virtual Keyboard Setting
        kb_check = Gtk.CheckButton(label="⌨️ Omogoči navidezno tipkovnico na zaslonu")
        kb_check.set_active(self.config.get("virtual_keyboard_enabled", False))
        kb_check.connect("toggled", lambda b: self.toggle_virtual_keyboard())
        box.pack_start(kb_check, False, False, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def create_main_webview(self):
        self.webview_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Main WebView: uses shared persistent web_context
        self.webview = WebKit2.WebView.new_with_context(self.web_context)
        self.setup_webview_settings(self.webview)

        # Connect signals
        self.webview.connect("load-changed", self.on_load_changed)
        self.webview.connect("notify::title", self.on_title_changed)
        self.webview.connect("notify::uri", self.on_uri_changed)
        self.webview.connect("create", self.on_create_webview)

        # Connect JavaScript Message Handlers
        content_mgr = self.webview.get_user_content_manager()
        content_mgr.register_script_message_handler("safeer")
        content_mgr.connect("script-message-received::safeer", self.on_js_message)

        # Inject YouTube zero-ad script ONLY ON YOUTUBE DOMAINS
        # This guarantees Google Search, Facebook, Banking, etc. receive 100% native untouched JS primitives!
        yt_script = WebKit2.UserScript(
            YOUTUBE_ADBLOCK_SCRIPT,
            WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.START,
            ["*://*.youtube.com/*", "*://youtube.com/*", "*://*.googlevideo.com/*"],
            None
        )
        content_mgr.add_script(yt_script)

        # Inject Generic cosmetic ad-blocker on content frames, excluding sensitive domains
        cosmetic_blocklist = [
            "*://*.google.com/*",
            "*://*.google.si/*",
            "*://*.facebook.com/*",
            "*://*.messenger.com/*",
            "*://accounts.google.com/*",
            "*://*.banka.si/*"
        ]
        gen_script = WebKit2.UserScript(
            GENERIC_COSMETIC_SCRIPT,
            WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.END,
            None,
            cosmetic_blocklist
        )
        content_mgr.add_script(gen_script)

        self.webview_container.pack_start(self.webview, True, True, 0)

    def setup_webview_settings(self, webview):
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
                self.webview.run_javascript(js_inject, None, None, None)
        except Exception as e:
            print(f"[Keyboard] Napaka: {e}")

    def load_homepage(self):
        home_path = os.path.join(BASE_DIR, "ui", "home.html")
        self.webview.load_uri(f"file://{home_path}")
        self.url_entry.set_text("safeer://home")

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

        self.webview.load_uri(target)

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

    def on_load_changed(self, webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            uri = webview.get_uri() or ""
            if "ui/home.html" in uri:
                self.url_entry.set_text("safeer://home")
            else:
                self.url_entry.set_text(uri)

    def on_title_changed(self, webview, prop):
        title = webview.get_title()
        if title:
            self.set_title(f"{title} — Safeer Browser (Linux Mint)")

    def on_uri_changed(self, webview, prop):
        uri = webview.get_uri()
        if uri and "ui/home.html" not in uri:
            self.url_entry.set_text(uri)

    def on_js_message(self, content_mgr, js_result):
        try:
            val = js_result.get_js_value()
            json_str = val.to_json(0)
            data = json.loads(json_str)
            action = data.get("action")
            if action == "navigate":
                url = data.get("url")
                if url:
                    self.webview.load_uri(url)
            elif action == "open_sidebar":
                service = data.get("service")
                if service == "settings":
                    self.open_settings_dialog()
                else:
                    self.toggle_sidebar_panel(service)
        except Exception as e:
            print(f"[IPC] Napaka: {e}")


def main():
    app = SafeerMintBrowser()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()

    # Respect startup settings
    if not app.config.get("sidebar_enabled", True):
        app.sidebar_box.hide()
        app.content_paned.set_position(0)
    else:
        app.sidebar_drawer.hide()
        app.content_paned.set_position(DOCK_WIDTH)

    if not app.config.get("virtual_keyboard_enabled", False):
        app.keyboard_box.hide()

    Gtk.main()


if __name__ == "__main__":
    main()
