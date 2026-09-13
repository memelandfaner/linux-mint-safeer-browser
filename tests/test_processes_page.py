"""safeer://procesi renders the monitor's data and its action links parse back (1.0.24)."""
import unittest

from core import processes_page


ROWS = [
    {"id": "t1", "title": "Facebook <script>", "cpu": 0.74, "rss_mb": 1229, "threads": 88, "active": True, "audio": False, "sleeping": False, "verdict": "hot"},
    {"id": "t2", "title": "YouTube Music", "cpu": 0.12, "rss_mb": 800, "threads": 45, "active": False, "audio": True, "sleeping": False, "verdict": "calm"},
    {"id": "t3", "title": "Stara stran", "cpu": 0.0, "rss_mb": 0, "threads": 0, "active": False, "audio": False, "sleeping": True, "verdict": "calm"},
]


class ProcessesPageTests(unittest.TestCase):
    def test_rows_are_escaped_sorted_and_summed(self):
        page = processes_page.render(ROWS, "sl", limit_mb=2048, cpu_budget=0.7)
        self.assertIn("Facebook &lt;script&gt;", page)
        self.assertLess(page.index("Facebook"), page.index("YouTube Music"))
        self.assertIn("74 %", page)
        self.assertIn("1,20 GB", page)
        self.assertIn("nad proračunom", page)
        self.assertIn("86 %", page)      # total CPU
        self.assertIn("1,98 GB", page)   # total memory
        self.assertIn("Meja pomnilnika na zavihek: 2048 MB", page)
        self.assertIn('http-equiv="refresh" content="3"', page)

    def test_actions_depend_on_state(self):
        page = processes_page.render(ROWS, "en")
        self.assertNotIn("safeer://procesi?spi=t1", page)   # active tab: no sleep link
        self.assertIn("safeer://procesi?spi=t2", page)
        self.assertNotIn("safeer://procesi?spi=t3", page)   # already sleeping
        self.assertIn("safeer://procesi?zapri=t3", page)
        self.assertIn("sleeping", page)
        self.assertIn("1.20 GB", page)

    def test_action_links_parse_and_others_do_not(self):
        self.assertEqual(processes_page.parse_action("safeer://procesi?spi=t2"), ("spi", "t2"))
        self.assertEqual(processes_page.parse_action("safeer://procesi?zapri=t3"), ("zapri", "t3"))
        self.assertEqual(processes_page.parse_action("safeer://procesi"), (None, None))
        self.assertEqual(processes_page.parse_action("https://example.com/?spi=t2"), (None, None))
        self.assertEqual(processes_page.parse_action("safeer://home?spi=t2"), (None, None))

    def test_browser_allows_the_page_and_registers_the_scheme(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "safeer_mint.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('u == "safeer://procesi" or u.startswith("safeer://procesi?")', source)
        self.assertEqual(source.count("self.register_internal_pages(self.web_context)"), 2)
        self.assertIn('context.register_uri_scheme("safeer", self.on_internal_page_request)', source)


if __name__ == "__main__":
    unittest.main()
