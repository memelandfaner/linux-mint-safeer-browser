"""Kopiranje povezav iz naslovne vrstice.

Matej, 13. 9. 2026: »težave s kopiranjem linkov v orodni vrstici«. Vzroki so bili trije:
prikazani naslov je brez »https://«, polni naslov se je vstavil šele po kliku (kazalec je
zato pristal osem znakov stran), označevanje z vlečenjem pa je prekinil select_region,
sprožen prek GLib.idle_add. Poleg tega ukaza »Kopiraj povezavo« ni bilo nikjer.
"""
import unittest
from types import SimpleNamespace

from safeer_mint import Gtk, SafeerMintBrowser, link_for_clipboard

POLNI = "https://www.rtvslo.si/novice/svet/clanek/123"
OKRNJEN = "www.rtvslo.si/novice/svet/clanek/123"


class OdlozisceLogika(unittest.TestCase):
    """Odločitev, ali ob Ctrl+C podtakniti polni naslov, je čista funkcija — preizkusljiva brez zaslona."""

    def test_a_whole_shortened_address_is_copied_as_a_real_link(self):
        self.assertTrue(link_for_clipboard(OKRNJEN, (0, len(OKRNJEN)), POLNI, OKRNJEN))

    def test_a_partial_selection_is_copied_exactly_as_selected(self):
        self.assertFalse(link_for_clipboard(OKRNJEN, (0, 12), POLNI, OKRNJEN))
        self.assertFalse(link_for_clipboard(OKRNJEN, (5, len(OKRNJEN)), POLNI, OKRNJEN))

    def test_text_the_user_typed_is_never_replaced(self):
        self.assertFalse(link_for_clipboard("kako speci kruh", (0, 15), POLNI, OKRNJEN))

    def test_nothing_to_fix_when_the_full_address_is_already_shown(self):
        self.assertFalse(link_for_clipboard(POLNI, (0, len(POLNI)), POLNI, OKRNJEN))

    def test_no_page_no_selection_no_change(self):
        self.assertFalse(link_for_clipboard(OKRNJEN, (0, len(OKRNJEN)), "", ""))
        self.assertFalse(link_for_clipboard(OKRNJEN, None, POLNI, OKRNJEN))
        self.assertFalse(link_for_clipboard("", (0, 0), POLNI, OKRNJEN))


def _brskalnik(uri=POLNI):
    """Najmanjši nadomestek brskalnika: metode kličemo nevezano, kot v ostalih preizkusih."""
    app = SimpleNamespace(_url_select_all_pending=False, _url_press_x=0.0, clipboard=[])
    app.get_active_webview = lambda: SimpleNamespace(get_uri=lambda: uri)
    app.current_page_uri = lambda: SafeerMintBrowser.current_page_uri(app)
    app.format_clean_url = lambda u: SafeerMintBrowser.format_clean_url(app, u)
    app.restore_full_url = lambda e: SafeerMintBrowser.restore_full_url(app, e)
    app.copy_to_clipboard = lambda t: (app.clipboard.append(t), True)[1]
    return app


class NaslovnaVrstica(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check()[0]:
            self.skipTest("potreben je zaslon")

    def test_the_full_address_is_in_place_before_the_click_moves_the_cursor(self):
        """Prej se je besedilo podaljšalo šele po kliku, zato je kazalec pristal drugje."""
        app = _brskalnik()
        entry = Gtk.Entry()
        entry.set_text(app.format_clean_url(POLNI))
        SafeerMintBrowser.on_url_button_press(
            app, entry, SimpleNamespace(x=40.0, button=1, type=None))
        self.assertEqual(entry.get_text(), POLNI)

    def test_dragging_keeps_the_selection_the_user_made(self):
        app = _brskalnik()
        entry = Gtk.Entry()
        entry.set_text(POLNI)
        app._url_select_all_pending = True
        app._url_press_x = 10.0
        entry.select_region(3, 9)
        SafeerMintBrowser.on_url_button_release(app, entry, SimpleNamespace(x=120.0))
        self.assertEqual(entry.get_selection_bounds(), (3, 9))
        self.assertFalse(app._url_select_all_pending)

    def test_a_click_without_dragging_selects_the_whole_address(self):
        app = _brskalnik()
        entry = Gtk.Entry()
        entry.set_text(POLNI)
        app._url_select_all_pending = True
        app._url_press_x = 10.0
        SafeerMintBrowser.on_url_button_release(app, entry, SimpleNamespace(x=11.0))
        self.assertEqual(entry.get_selection_bounds(), (0, len(POLNI)))

    def test_what_the_user_typed_survives_coming_back_to_the_window(self):
        """Prej je on_url_focus_in besedilo prepisal brez pogoja in natipkano se je izgubilo."""
        app = _brskalnik()
        entry = Gtk.Entry()
        entry.set_text("kako speci kruh")
        SafeerMintBrowser.restore_full_url(app, entry)
        self.assertEqual(entry.get_text(), "kako speci kruh")

    def test_copying_the_whole_address_puts_a_real_link_on_the_clipboard(self):
        app = _brskalnik()
        entry = Gtk.Entry()
        entry.set_text(app.format_clean_url(POLNI))
        entry.select_region(0, -1)
        SafeerMintBrowser.on_url_copy_clipboard(app, entry)
        self.assertEqual(app.clipboard, [POLNI])

    def test_copying_a_part_of_the_address_is_left_alone(self):
        app = _brskalnik()
        entry = Gtk.Entry()
        entry.set_text(app.format_clean_url(POLNI))
        entry.select_region(0, 12)
        SafeerMintBrowser.on_url_copy_clipboard(app, entry)
        self.assertEqual(app.clipboard, [])

    def test_the_right_click_menu_offers_copy_link(self):
        app = _brskalnik()
        menu = Gtk.Menu()
        SafeerMintBrowser.on_url_populate_popup(app, Gtk.Entry(), menu)
        oznake = [o.get_label() for o in menu.get_children() if isinstance(o, Gtk.MenuItem)]
        self.assertTrue(any("Kopiraj povezavo" in (o or "") for o in oznake), oznake)

    def test_there_is_no_menu_item_without_a_page(self):
        app = _brskalnik(uri="")
        menu = Gtk.Menu()
        SafeerMintBrowser.on_url_populate_popup(app, Gtk.Entry(), menu)
        self.assertEqual(menu.get_children(), [])


if __name__ == "__main__":
    unittest.main()
