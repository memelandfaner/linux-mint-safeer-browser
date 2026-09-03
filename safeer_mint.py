#!/usr/bin/env python3
"""
Safeer Browser for Linux Mint
Desktop-optimized browser with Modular Sidebar (Messenger, Gmail, Custom sites),
Privacy Shield, and Optional Virtual Keyboard.
"""

import os
import sys
import json
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, Gdk, WebKit2, GLib, Gio

# Import core modules
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core.config import ConfigManager
from core.adblock import YOUTUBE_ADBLOCK_SCRIPT, is_threat_domain

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


class SafeerMintBrowser(Gtk.Window):
    def __init__(self):
        super().__init__(title="Safeer Browser — Linux Mint Edition")
        self.set_default_size(1280, 800)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.config = ConfigManager()
        self.active_sidebar_service = None

        # Apply Linux Mint Dark Theme preference
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        self.setup_ui()
        self.apply_css()

        # Connect F4 keyboard shortcut to toggle sidebar
        self.connect("key-press-event", self.on_global_key_press)

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

        # Check permanent sidebar setting
        if not self.config.get("sidebar_enabled", True):
            self.sidebar_box.hide()

        # Load initial start page
        self.load_homepage()

    def apply_css(self):
        css_provider = Gtk.CssProvider()
        css_data = """
        window { background-color: #060911; }
        .top-toolbar {
            background-color: #0d1322;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding: 6px 12px;
        }
        .nav-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            color: #cbd5e1;
            padding: 5px 12px;
            margin-right: 4px;
            font-size: 13px;
        }
        .nav-btn:hover {
            background: rgba(0, 210, 255, 0.15);
            border-color: #00d2ff;
            color: #fff;
        }
        .nav-btn.active {
            background: rgba(0, 210, 255, 0.25);
            border-color: #00d2ff;
            color: #00d2ff;
        }
        .url-entry {
            background: #080c16;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 999px;
            color: #fff;
            padding: 6px 16px;
            font-size: 13.5px;
        }
        .url-entry:focus {
            border-color: #00d2ff;
            box-shadow: 0 0 8px rgba(0, 210, 255, 0.3);
        }
        .dock-bar {
            background-color: #080c16;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            padding: 6px 4px;
        }
        .dock-btn {
            background: transparent;
            border: none;
            border-radius: 12px;
            padding: 10px;
            margin: 3px 2px;
            color: #94a3b8;
            font-size: 20px;
        }
        .dock-btn:hover {
            background: rgba(0, 210, 255, 0.15);
            color: #00d2ff;
        }
        .dock-btn.active {
            background: rgba(0, 210, 255, 0.25);
            border: 1px solid rgba(0, 210, 255, 0.5);
            color: #00d2ff;
        }
        .btn-delete {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #ef4444;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 12px;
        }
        .btn-delete:hover {
            background: #ef4444;
            color: #fff;
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

        # Back
        self.btn_back = Gtk.Button(label="◀")
        self.btn_back.get_style_context().add_class("nav-btn")
        self.btn_back.connect("clicked", lambda b: self.webview.go_back())
        self.top_bar.pack_start(self.btn_back, False, False, 0)

        # Forward
        self.btn_forward = Gtk.Button(label="▶")
        self.btn_forward.get_style_context().add_class("nav-btn")
        self.btn_forward.connect("clicked", lambda b: self.webview.go_forward())
        self.top_bar.pack_start(self.btn_forward, False, False, 0)

        # Reload
        self.btn_reload = Gtk.Button(label="⟳")
        self.btn_reload.get_style_context().add_class("nav-btn")
        self.btn_reload.connect("clicked", lambda b: self.webview.reload())
        self.top_bar.pack_start(self.btn_reload, False, False, 0)

        # Home
        self.btn_home = Gtk.Button(label="🏠")
        self.btn_home.get_style_context().add_class("nav-btn")
        self.btn_home.connect("clicked", lambda b: self.load_homepage())
        self.top_bar.pack_start(self.btn_home, False, False, 0)

        # Omnibox / URL Entry
        self.url_entry = Gtk.Entry()
        self.url_entry.get_style_context().add_class("url-entry")
        self.url_entry.set_placeholder_text("Vnesite naslov spletnega mesta ali iskanje...")
        self.url_entry.connect("activate", self.on_url_activate)
        self.top_bar.pack_start(self.url_entry, True, True, 4)

        # Shield Status indicator
        self.shield_indicator = Gtk.Label(label="🛡️ Ščit aktiven")
        self.shield_indicator.get_style_context().add_class("nav-btn")
        self.top_bar.pack_start(self.shield_indicator, False, False, 4)

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

    def toggle_sidebar_visibility(self):
        """Začasno skrije ali prikaže celotno stransko vrstico."""
        if self.sidebar_box.is_visible():
            self.sidebar_box.hide()
            self.btn_sidebar.get_style_context().remove_class("active")
        else:
            self.sidebar_box.show_all()
            # If the drawer wasn't open, keep it hidden
            if not self.active_sidebar_service:
                self.sidebar_drawer.hide()
            self.btn_sidebar.get_style_context().add_class("active")

    def create_sidebar(self):
        # Outer sidebar box: icon dock strip + slide-out webview drawer
        self.sidebar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        # 1. Left Icon Dock
        self.icon_dock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.icon_dock.get_style_context().add_class("dock-bar")
        self.sidebar_box.pack_start(self.icon_dock, False, False, 0)

        # 2. Slide-out Panel (Drawer)
        self.sidebar_drawer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.sidebar_drawer.set_size_request(420, -1)
        self.sidebar_drawer.set_no_show_all(True)
        self.sidebar_drawer.hide()

        # Drawer Header
        self.drawer_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.drawer_header.get_style_context().add_class("top-toolbar")
        self.drawer_title = Gtk.Label(label="Stranska integracija")
        self.drawer_title.set_halign(Gtk.Align.START)
        self.drawer_header.pack_start(self.drawer_title, True, True, 6)

        btn_close_drawer = Gtk.Button(label="✕")
        btn_close_drawer.get_style_context().add_class("nav-btn")
        btn_close_drawer.connect("clicked", lambda b: self.close_sidebar_panel())
        self.drawer_header.pack_end(btn_close_drawer, False, False, 0)

        self.sidebar_drawer.pack_start(self.drawer_header, False, False, 0)

        # Drawer WebView
        self.sidebar_webview = WebKit2.WebView()
        self.setup_webview_settings(self.sidebar_webview)
        self.sidebar_drawer.pack_start(self.sidebar_webview, True, True, 0)

        self.sidebar_box.pack_start(self.sidebar_drawer, False, False, 0)

        # Populate icon dock with current integrations
        self.rebuild_icon_dock()

    def rebuild_icon_dock(self):
        """Dinamično ponovno zgradi ikone v stranski orodni vrstici."""
        # Clear existing children in icon_dock
        for child in self.icon_dock.get_children():
            self.icon_dock.remove(child)

        integrations = self.config.get("integrations", {})
        for s_id, s_data in integrations.items():
            if s_data.get("enabled", True):
                btn = Gtk.Button(label=s_data.get("icon", "🌐"))
                btn.set_tooltip_text(f"{s_data.get('name', 'Stran')} ({s_data.get('url', '')})")
                btn.get_style_context().add_class("dock-btn")
                btn.connect("clicked", lambda b, sid=s_id: self.toggle_sidebar_panel(sid))
                self.icon_dock.pack_start(btn, False, False, 0)

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
        dialog.set_default_size(360, 220)

        box = dialog.get_content_area()
        box.set_spacing(10)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        lbl_name = Gtk.Label(label="Ime spletne strani (npr. WhatsApp, ChatGPT):")
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

        lbl_icon = Gtk.Label(label="Ikona ali simbol (npr. 💬, 🤖, 🎧, 🌐):")
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
                self.config.add_integration(name, url, icon)
                self.rebuild_icon_dock()

        dialog.destroy()

    def open_settings_dialog(self):
        """Celovit dialog za nastavitve stranske vrstice in brskalnika."""
        dialog = Gtk.Dialog(
            title="Nastavitve Safeer Browser",
            transient_for=self,
            flags=0
        )
        dialog.add_buttons("Zapri", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(480, 480)

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
                self.sidebar_box.show_all()
                if not self.active_sidebar_service:
                    self.sidebar_drawer.hide()
            else:
                self.sidebar_box.hide()

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
        scrolled.set_min_content_height(160)
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

    def toggle_sidebar_panel(self, service_id: str):
        if self.active_sidebar_service == service_id and self.sidebar_drawer.is_visible():
            self.close_sidebar_panel()
            return

        integrations = self.config.get("integrations", {})
        if service_id in integrations:
            service = integrations[service_id]
            self.drawer_title.set_text(f"{service.get('icon', '')} {service.get('name', '')}")
            self.sidebar_webview.load_uri(service.get("url", ""))
            self.sidebar_drawer.show_all()
            self.active_sidebar_service = service_id

    def close_sidebar_panel(self):
        self.sidebar_drawer.hide()
        self.active_sidebar_service = None

    def create_main_webview(self):
        self.webview_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.webview = WebKit2.WebView()
        self.setup_webview_settings(self.webview)

        # Connect signals
        self.webview.connect("load-changed", self.on_load_changed)
        self.webview.connect("notify::title", self.on_title_changed)
        self.webview.connect("notify::uri", self.on_uri_changed)

        # Connect JavaScript Message Handlers
        content_mgr = self.webview.get_user_content_manager()
        content_mgr.register_script_message_handler("safeer")
        content_mgr.connect("script-message-received::safeer", self.on_js_message)

        # Inject YouTube ad-blocker user script
        ad_script = WebKit2.UserScript(
            YOUTUBE_ADBLOCK_SCRIPT,
            WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.START,
            None,
            None
        )
        content_mgr.add_script(ad_script)

        self.webview_container.pack_start(self.webview, True, True, 0)

    def setup_webview_settings(self, webview):
        settings = webview.get_settings()
        settings.set_enable_developer_extras(True)
        settings.set_enable_webaudio(True)
        settings.set_enable_webgl(True)
        settings.set_enable_media_stream(True)
        settings.set_user_agent(USER_AGENT)

    def create_keyboard_panel(self):
        self.keyboard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.keyboard_box.set_size_request(-1, 240)
        self.keyboard_box.set_no_show_all(True)

        # Load virtual keyboard webview
        self.kb_webview = WebKit2.WebView()
        self.setup_webview_settings(self.kb_webview)
        kb_path = os.path.join(BASE_DIR, "ui", "keyboard.html")
        self.kb_webview.load_uri(f"file://{kb_path}")

        # Connect keyboard message handler
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
        else:
            self.keyboard_box.hide()
            self.btn_keyboard.set_label("⌨️ Tipkovnica")

    def on_keyboard_message(self, content_mgr, js_result):
        try:
            val = js_result.get_js_value()
            json_str = val.to_json(0)
            data = json.loads(json_str)
            if data.get("action") == "close":
                self.toggle_virtual_keyboard()
            elif "key" in data:
                key = data["key"]
                # Forward key event to active webview
                js_inject = f"""
                (function() {{
                    const el = document.activeElement;
                    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) {{
                        if ('{key}' === 'Backspace') {{
                            el.value = el.value.slice(0, -1);
                        }} else if ('{key}' === 'Enter') {{
                            if (el.form) el.form.submit();
                        }} else {{
                            el.value = (el.value || '') + '{key}';
                        }}
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                }})();
                """
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
                target = f"https://www.google.com/search?q={text}"
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
            self.set_title(f"{title} — Safeer Browser")

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
    # Respect settings on launch
    if not app.config.get("sidebar_enabled", True):
        app.sidebar_box.hide()
    else:
        app.sidebar_drawer.hide()

    if not app.config.get("virtual_keyboard_enabled", False):
        app.keyboard_box.hide()

    Gtk.main()


if __name__ == "__main__":
    main()
