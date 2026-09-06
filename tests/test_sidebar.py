"""Exercise the real GTK dock with enabled saved integrations (requires a display)."""
import unittest
from types import SimpleNamespace
from safeer_mint import Gtk, SafeerMintBrowser


class SidebarTests(unittest.TestCase):
    def test_saved_integrations_create_buttons_and_survive_rebuild(self):
        if not Gtk.init_check()[0]:
            self.skipTest("GTK display required")
        integrations = {
            "music": {"name": "Music", "url": "https://example.org/", "icon": "M"},
            "same": {"name": "https://example.net/", "url": "https://example.net/"},
            "disabled": {"name": "Hidden", "enabled": False},
        }
        opened = []
        app = SimpleNamespace(
            config={"integrations": integrations}, icon_dock=Gtk.Box(),
            active_sidebar_service="music", toggle_sidebar_panel=opened.append,
            open_add_page_dialog=lambda: None, open_settings_dialog=lambda: None,
        )
        for _ in range(2):
            SafeerMintBrowser.rebuild_icon_dock(app)
            self.assertEqual(set(app.dock_buttons), {"music", "same"})
            self.assertEqual(len(app.icon_dock.get_children()), 5)
            self.assertEqual(app.dock_buttons["music"].get_label(), "M")
            self.assertEqual(app.dock_buttons["music"].get_tooltip_text(), "Music\nhttps://example.org/")
            self.assertEqual(app.dock_buttons["same"].get_tooltip_text(), "https://example.net/")
            self.assertTrue(app.dock_buttons["music"].get_style_context().has_class("active"))
            app.dock_buttons["music"].emit("clicked")
            app.dock_buttons["same"].emit("clicked")
        self.assertEqual(opened, ["music", "same", "music", "same"])
        app.icon_dock.destroy()
