#!/usr/bin/env python3
"""
Safeer Browser for Linux Mint
Desktop-optimized browser with Modular Sidebar (Messenger, Gmail, YouTube),
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
        super().__init__(title="Safeer Browser - Linux Mint Edition")
        self.set_default_size(1280, 800)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.config = ConfigManager()
        self.active_sidebar_service = None

        # Apply Linux Mint Dark Theme preference
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        self.setup_ui()
        self.apply_css()

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
            padding: 4px 10px;
            margin-right: 4px;
        }
        .nav-btn:hover {
            background: rgba(0, 210, 255, 0.15);
            border-color: #00d2ff;
            color: #fff;
        }
        .url-entry {
            background: #080c16;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 999px;
            color: #fff;
            padding: 6px 16px;
            font-size: 13px;
        }
        .url-entry:focus {
            border-color: #00d2ff;
            box-shadow: 0 0 8px rgba(0, 210, 255, 0.3);
        }
        .dock-bar {
            background-color: #090e1a;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        .dock-btn {
            background: transparent;
            border: none;
            border-radius: 12px;
            padding: 10px;
            margin: 4px;
            color: #94a3b8;
            font-size: 18px;
        }
        .dock-btn:hover, .dock-btn.active {
            background: rgba(0, 210, 255, 0.15);
            color: #00d2ff;
        }
        """
        css_provider.load_from_data(css_data.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

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
        self.shield_indicator = Gtk.Label(label="🛡️ Ščit vklopljen")
        self.shield_indicator.get_style_context().add_class("nav-btn")
        self.top_bar.pack_start(self.shield_indicator, False, False, 4)

        # Optional Virtual Keyboard Toggle Button (Default OFF)
        self.btn_keyboard = Gtk.Button(label="⌨️ Tipkovnica")
        self.btn_keyboard.get_style_context().add_class("nav-btn")
        self.btn_keyboard.set_tooltip_text("Vklopi/izklopi navidezno tipkovnico na zaslonu")
        self.btn_keyboard.connect("clicked", self.toggle_virtual_keyboard)
        self.top_bar.pack_start(self.btn_keyboard, False, False, 0)

    def create_sidebar(self):
        # Outer sidebar box: icon dock strip + slide-out webview drawer
        self.sidebar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        # 1. Left Icon Dock
        self.icon_dock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.icon_dock.get_style_context().add_class("dock-bar")
        self.sidebar_box.pack_start(self.icon_dock, False, False, 0)

        integrations = self.config.get("integrations", {})

        # Messenger Button
        if integrations.get("messenger", {}).get("enabled", True):
            btn_msg = Gtk.Button(label="💬")
            btn_msg.set_tooltip_text("Facebook Messenger")
            btn_msg.get_style_context().add_class("dock-btn")
            btn_msg.connect("clicked", lambda b: self.toggle_sidebar_panel("messenger"))
            self.icon_dock.pack_start(btn_msg, False, False, 0)

        # Gmail Button
        if integrations.get("gmail", {}).get("enabled", True):
            btn_gmail = Gtk.Button(label="✉️")
            btn_gmail.set_tooltip_text("Gmail")
            btn_gmail.get_style_context().add_class("dock-btn")
            btn_gmail.connect("clicked", lambda b: self.toggle_sidebar_panel("gmail"))
            self.icon_dock.pack_start(btn_gmail, False, False, 0)

        # YouTube Button
        if integrations.get("youtube", {}).get("enabled", True):
            btn_yt = Gtk.Button(label="📺")
            btn_yt.set_tooltip_text("YouTube (Brez oglasov)")
            btn_yt.get_style_context().add_class("dock-btn")
            btn_yt.connect("clicked", lambda b: self.toggle_sidebar_panel("youtube"))
            self.icon_dock.pack_start(btn_yt, False, False, 0)

        # Spacer
        spacer = Gtk.Box()
        self.icon_dock.pack_start(spacer, True, True, 0)

        # Settings Button
        btn_settings = Gtk.Button(label="⚙️")
        btn_settings.set_tooltip_text("Nastavitve integracij")
        btn_settings.get_style_context().add_class("dock-btn")
        btn_settings.connect("clicked", lambda b: self.open_settings_dialog())
        self.icon_dock.pack_start(btn_settings, False, False, 0)

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

    def open_settings_dialog(self):
        dialog = Gtk.Dialog(
            title="Nastavitve integracij Safeer Browser",
            transient_for=self,
            flags=0
        )
        dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        dialog.set_default_size(400, 300)

        box = dialog.get_content_area()
        box.set_spacing(12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        title = Gtk.Label(label="<b>Vklop ali izklop integracij v stranski vrstici:</b>")
        title.set_use_markup(True)
        title.set_halign(Gtk.Align.START)
        box.pack_start(title, False, False, 0)

        integrations = self.config.get("integrations", {})
        for k, v in integrations.items():
            check = Gtk.CheckButton(label=f"{v.get('icon', '')} {v.get('name', '')}")
            check.set_active(v.get("enabled", True))

            def on_toggled(btn, item_key=k):
                self.config.settings["integrations"][item_key]["enabled"] = btn.get_active()
                self.config.save_settings()

            check.connect("toggled", on_toggled)
            box.pack_start(check, False, False, 0)

        # Virtual Keyboard Setting
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep, False, False, 6)

        kb_check = Gtk.CheckButton(label="⌨️ Omogoči navidezno tipkovnico na zaslonu")
        kb_check.set_active(self.config.get("virtual_keyboard_enabled", False))
        kb_check.connect("toggled", lambda b: self.toggle_virtual_keyboard())
        box.pack_start(kb_check, False, False, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

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
                engine = self.config.get("search_engine", "google")
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
    # Ensure virtual keyboard stays hidden by default if not set
    if not app.config.get("virtual_keyboard_enabled", False):
        app.keyboard_box.hide()
    Gtk.main()


if __name__ == "__main__":
    main()
