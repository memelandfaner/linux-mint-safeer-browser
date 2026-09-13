"""The per-tab monitor reads /proc and turns it into calm / hot / hog verdicts (1.0.24)."""
import os
import tempfile
import unittest

from core import tab_monitor
from core.tab_monitor import TabMonitor, describe


def _write_proc(root, pid, ticks, rss_pages=1000, threads=7):
    os.makedirs(os.path.join(root, str(pid)), exist_ok=True)
    utime, stime = ticks // 2, ticks - ticks // 2
    fields = ["S", "1", "1", "1", "0", "-1", "4194560", "0", "0", "0", "0", str(utime), str(stime), "0", "0", "20", "0", str(threads), "0", "0"]
    with open(os.path.join(root, str(pid), "stat"), "w") as handle:
        handle.write(f"{pid} (WebKitWebProcess 13 99) " + " ".join(fields) + "\n")
    with open(os.path.join(root, str(pid), "statm"), "w") as handle:
        handle.write(f"{rss_pages * 2} {rss_pages} 100 1 0 200 0\n")


class TabMonitorTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.monitor = TabMonitor(cpu_budget=0.5, memory_budget_mb=1024, show_after=10, patience=60, proc=self.root)
        self.mb_pages = 1024 // tab_monitor.PAGE_KB  # pages per MB

    def test_cpu_share_and_memory_come_from_two_samples(self):
        _write_proc(self.root, 500, ticks=1000, rss_pages=300 * self.mb_pages)
        first = self.monitor.sample([("t1", 500, True, False)], now=100.0)
        self.assertEqual(first["t1"].cpu, 0.0)  # no delta yet
        self.assertEqual(first["t1"].rss_mb, 300)
        self.assertEqual(first["t1"].threads, 7)
        _write_proc(self.root, 500, ticks=1000 + int(0.75 * 2 * tab_monitor.CLK_TCK))
        second = self.monitor.sample([("t1", 500, True, False)], now=102.0)
        self.assertAlmostEqual(second["t1"].cpu, 0.75, places=2)
        self.assertEqual(second["t1"].verdict, "calm")  # over budget, but not for long

    def test_hot_after_ten_seconds_and_hog_after_a_minute(self):
        verdicts = []
        for now in (0.0, 2.0, 12.0, 30.0, 63.0):
            # a constant 90 % of one core between samples
            _write_proc(self.root, 501, ticks=int(0.9 * now * tab_monitor.CLK_TCK))
            verdicts.append(self.monitor.sample([("t1", 501, False, False)], now=now)["t1"].verdict)
        # first sample has no delta; over budget from t=2 on: hot at t>=12, hog at t>=62
        self.assertEqual(verdicts, ["calm", "calm", "hot", "hot", "hog"])

    def test_memory_alone_counts_as_over_budget(self):
        _write_proc(self.root, 502, ticks=0, rss_pages=1500 * self.mb_pages)
        self.monitor.sample([("t1", 502, False, True)], now=0.0)
        _write_proc(self.root, 502, ticks=0, rss_pages=1500 * self.mb_pages)
        sample = self.monitor.sample([("t1", 502, False, True)], now=11.0)["t1"]
        self.assertEqual(sample.verdict, "hot")
        self.assertTrue(sample.audio)

    def test_going_calm_resets_the_clock(self):
        _write_proc(self.root, 503, ticks=0, rss_pages=2000 * self.mb_pages)
        self.monitor.sample([("t1", 503, False, False)], now=0.0)
        _write_proc(self.root, 503, ticks=0, rss_pages=100 * self.mb_pages)
        sample = self.monitor.sample([("t1", 503, False, False)], now=30.0)["t1"]
        self.assertEqual(sample.verdict, "calm")
        self.assertIsNone(sample.over_since)

    def test_missing_process_and_missing_pid_are_harmless(self):
        result = self.monitor.sample([("t1", 999999, True, False), ("t2", 0, False, False)], now=0.0)
        self.assertEqual(result["t1"].cpu, 0.0)
        self.assertEqual(result["t2"].rss_mb, 0)
        self.assertEqual(self.monitor._last, {})

    def test_describe_is_short_and_localised(self):
        sample = self.monitor.sample([], now=0.0)
        from core.tab_monitor import TabSample
        s = TabSample(tab_id="x", cpu=0.741, rss_mb=1229)
        self.assertEqual(describe(s), "CPU 74 % · 1,2 GB")
        self.assertEqual(describe(s, "en"), "CPU 74 % · 1.2 GB")
        self.assertEqual(describe(TabSample(tab_id="y", cpu=0.05, rss_mb=300)), "CPU 5 % · 300 MB")

    def test_real_proc_of_this_process(self):
        monitor = TabMonitor()
        first = monitor.sample([("me", os.getpid(), True, False)])
        self.assertGreater(first["me"].rss_mb, 1)
        self.assertGreater(first["me"].threads, 0)


if __name__ == "__main__":
    unittest.main()
