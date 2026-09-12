import unittest
from pathlib import Path

SMOKE = Path(__file__).resolve().parents[1] / "safeer_windows" / "smoke.py"


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
