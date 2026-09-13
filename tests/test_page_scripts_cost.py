"""The periodic page scripts must stay cheap on huge pages and idle in hidden tabs.

Background (1.0.24): a Facebook tab kept one core busy and the browser stopped answering clicks.
Part of that cost was ours: three scripts polled the whole DOM on fixed timers. Now every scan
is paced by how long it took, waits for an idle slot, does nothing while the tab is hidden, and
the overlay check asks for the few elements on top instead of walking every node.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from core.adblock import (
    ADGUARD_PROTECTION_SCRIPT,
    ANTI_CLICKJACKING_SCRIPT,
    GENERIC_COSMETIC_SCRIPT,
    PAGE_TASK_SCHEDULER_JS,
)


class PageScriptPacingTests(unittest.TestCase):
    def test_periodic_scripts_use_the_shared_scheduler_not_fixed_timers(self):
        for script in (ADGUARD_PROTECTION_SCRIPT, GENERIC_COSMETIC_SCRIPT, ANTI_CLICKJACKING_SCRIPT):
            self.assertIn("window.__safeerSchedule(", script)
            self.assertNotIn("setInterval(", script)
            self.assertIn("if (document.hidden)", script)
            self.assertIn("requestIdleCallback", script)

    def test_overlay_check_asks_for_elements_on_top_instead_of_walking_the_dom(self):
        self.assertIn("elementsFromPoint", ANTI_CLICKJACKING_SCRIPT)
        self.assertNotIn("querySelectorAll('div, a, span')", ANTI_CLICKJACKING_SCRIPT)

    def test_scheduler_is_defined_once_per_page(self):
        self.assertIn("if (!window.__safeerSchedule)", PAGE_TASK_SCHEDULER_JS)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_scripts_are_valid_javascript(self):
        for script in (ADGUARD_PROTECTION_SCRIPT, GENERIC_COSMETIC_SCRIPT, ANTI_CLICKJACKING_SCRIPT):
            with tempfile.NamedTemporaryFile("w", suffix=".js") as handle:
                handle.write(script)
                handle.flush()
                subprocess.run(["node", "--check", handle.name], check=True)


def _chromium_path():
    path = os.environ.get("SAFEER_CHROMIUM", "")
    return path if path and os.path.exists(path) else ""


@unittest.skipUnless(_chromium_path(), "set SAFEER_CHROMIUM to a Chromium binary to run the browser tests")
class PageScriptBrowserTests(unittest.TestCase):
    def _page(self, html, script):
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(executable_path=_chromium_path(), args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        context.route("https://example.test/**", lambda route: route.fulfill(
            status=200, content_type="text/html", body=html))
        context.add_init_script(script)
        page = context.new_page()
        page.goto("https://example.test/")
        self.addCleanup(pw.stop)
        self.addCleanup(browser.close)
        return page

    def test_invisible_overlay_is_removed_but_a_dialog_with_a_button_stays(self):
        html = """<!doctype html><html><body>
        <p>content</p>
        <div id="trap" style="position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:5000;background:transparent"></div>
        <div id="dialog" role="dialog" style="position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:4000;background:transparent"><button>OK</button></div>
        </body></html>"""
        page = self._page(html, ANTI_CLICKJACKING_SCRIPT)
        page.wait_for_function("!document.getElementById('trap')", timeout=5000)
        self.assertIsNotNone(page.query_selector("#dialog"))

    def test_overlay_check_costs_the_same_on_a_feed_with_seventy_thousand_nodes(self):
        post = "<span>post</span><a href='#'>x</a><div role='button'>like</div>"
        for depth in range(20):
            post = f"<div class='w{depth}'>{post}</div>"
        html = "<!doctype html><html><body><div id='feed'>" + post * 3000 + "</div></body></html>"
        page = self._page(html, ANTI_CLICKJACKING_SCRIPT)
        nodes = page.evaluate("document.querySelectorAll('div, a, span').length")
        self.assertGreater(nodes, 60000)
        body = ANTI_CLICKJACKING_SCRIPT.split("function candidatesAt", 1)[1].split("\n    if (document.body)")[0]
        took = page.evaluate("() => { function candidatesAt" + body + "; const t0 = performance.now(); "
                             "neutralizeClickjackingOverlays(); return performance.now() - t0; }")
        self.assertLess(took, 25, f"overlay check took {took:.1f} ms on {nodes} nodes")

    def test_scheduler_skips_hidden_tabs_and_backs_off_after_a_slow_scan(self):
        html = "<!doctype html><html><body><p>x</p></body></html>"
        page = self._page(html, PAGE_TASK_SCHEDULER_JS)
        # Hidden: the task must not run at all.
        page.evaluate("""() => {
            Object.defineProperty(document, 'hidden', { value: true, configurable: true });
            window.runs = 0;
            window.__safeerSchedule(() => { window.runs++; }, 50);
        }""")
        page.wait_for_timeout(400)
        self.assertEqual(page.evaluate("window.runs"), 0)
        # Visible again: it runs, and a slow task is rescheduled much later than its base interval.
        page.evaluate("""() => {
            Object.defineProperty(document, 'hidden', { value: false, configurable: true });
            document.dispatchEvent(new Event('visibilitychange'));
            window.slowRuns = [];
            window.__safeerSchedule(() => { const t = performance.now(); window.slowRuns.push(t); while (performance.now() - t < 40) {} }, 50, 100000);
        }""")
        page.wait_for_function("window.runs >= 1", timeout=3000)
        page.wait_for_function("window.slowRuns.length >= 1", timeout=3000)
        page.wait_for_timeout(1200)
        slow_runs = page.evaluate("window.slowRuns")
        # 40 ms of work -> next run no sooner than ~2 s (50x), so at most one more run in 1.2 s.
        self.assertLessEqual(len(slow_runs), 2, slow_runs)
        if len(slow_runs) == 2:
            self.assertGreaterEqual(slow_runs[1] - slow_runs[0], 1000)


if __name__ == "__main__":
    unittest.main()
