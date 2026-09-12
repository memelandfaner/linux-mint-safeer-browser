import unittest
from pathlib import Path

SMOKE = Path(__file__).resolve().parents[1] / "safeer_windows" / "smoke.py"
BROWSER = Path(__file__).resolve().parents[1] / "safeer_windows" / "browser.py"


class SmokeWatchdogTests(unittest.TestCase):
    """A hung event loop used to end as a bare subprocess timeout with no report to look at."""

    def setUp(self):
        self.source = SMOKE.read_text(encoding="utf-8")

    def test_thread_watchdog_is_armed_after_the_qt_one(self):
        start = self.source.index("def start(")
        block = self.source[start:self.source.index("def watchdog(", start)]
        self.assertIn("QTimer.singleShot(int(limit * 1000), self.watchdog)", block)
        self.assertIn("self.hard_watchdog(limit + 60)", block)

    def test_hung_run_writes_a_report_and_stops_the_process(self):
        start = self.source.index("def hard_watchdog(")
        block = self.source[start:self.source.index("timer.start()", start)]
        self.assertIn("threading.Timer", self.source[start:])
        self.assertIn('"failed": ["hung"]', block)
        self.assertIn("last_check", block)
        self.assertIn("os._exit(3)", block)
        self.assertLess(block.index("json.dump(report"), block.index("os._exit(3)"))


if __name__ == "__main__":
    unittest.main()


class NoModalDuringSmokeTests(unittest.TestCase):
    """A modal dialog in an automated run blocks the event loop until the job is killed."""

    def setUp(self):
        self.source = BROWSER.read_text(encoding="utf-8")

    def _block(self, start_marker, end_marker="\n    def "):
        start = self.source.index(start_marker)
        return self.source[start:self.source.index(end_marker, start + len(start_marker))]

    def test_external_link_question_is_skipped(self):
        block = self._block("def confirm_external(")
        self.assertIn("if self.app.smoke:", block)
        self.assertLess(block.index("self.app.smoke"), block.index("QMessageBox.question"))

    def test_page_dialogs_are_answered_without_a_window(self):
        for name, expected in (("javaScriptAlert", "return\n"), ("javaScriptConfirm", "return False"),
                               ("javaScriptPrompt", 'return False, ""')):
            block = self._block(f"def {name}(")
            self.assertIn("if self.window_ref.app.smoke:", block, name)
            self.assertIn(expected, block, name)
            self.assertLess(block.index("smoke"), block.index("super()"), name)
