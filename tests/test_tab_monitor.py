"""The per-tab monitor reads /proc and turns it into calm / hot / hog verdicts (1.0.24)."""
import os
import tempfile
import unittest

from core import tab_monitor
from core.tab_monitor import TabMonitor, describe


def _write_proc(root, pid, ticks, rss_pages=1000, threads=7, parent=1000):
    """A fake WebKitWebProcess under <root>/<parent> -> bwrap -> pid (like the real sandbox tree)."""
    os.makedirs(os.path.join(root, str(pid)), exist_ok=True)
    bwrap = pid * 10
    os.makedirs(os.path.join(root, str(parent), "task", str(parent)), exist_ok=True)
    kids_path = os.path.join(root, str(parent), "task", str(parent), "children")
    kids = set()
    if os.path.exists(kids_path):
        with open(kids_path) as handle:
            kids = set(handle.read().split())
    kids.add(str(bwrap))
    with open(kids_path, "w") as handle:
        handle.write(" ".join(sorted(kids)) + "\n")
    os.makedirs(os.path.join(root, str(bwrap), "task", str(bwrap)), exist_ok=True)
    with open(os.path.join(root, str(bwrap), "comm"), "w") as handle:
        handle.write("bwrap\n")
    with open(os.path.join(root, str(bwrap), "task", str(bwrap), "children"), "w") as handle:
        handle.write(f"{pid}\n")
    with open(os.path.join(root, str(pid), "comm"), "w") as handle:
        handle.write("WebKitWebProces\n")
    utime, stime = ticks // 2, ticks - ticks // 2
    fields = ["S", "1", "1", "1", "0", "-1", "4194560", "0", "0", "0", "0", str(utime), str(stime), "0", "0", "20", "0", str(threads), "0", "0"]
    with open(os.path.join(root, str(pid), "stat"), "w") as handle:
        handle.write(f"{pid} (WebKitWebProcess 13 99) " + " ".join(fields) + "\n")
    with open(os.path.join(root, str(pid), "statm"), "w") as handle:
        handle.write(f"{rss_pages * 2} {rss_pages} 100 1 0 200 0\n")


class TabMonitorTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.monitor = TabMonitor(cpu_budget=0.5, memory_budget_mb=1024, show_after=10, patience=60, proc=self.root, root_pid=1000)
        self.mb_pages = 1024 // tab_monitor.PAGE_KB  # pages per MB

    def test_cpu_share_and_memory_come_from_two_samples(self):
        _write_proc(self.root, 500, ticks=1000, rss_pages=300 * self.mb_pages)
        first = self.monitor.sample([("t1", 99.0, True, False)], now=100.0)
        self.assertEqual(self.monitor.pid_of("t1"), 500)
        self.assertEqual(first["t1"].cpu, 0.0)  # no delta yet
        self.assertEqual(first["t1"].rss_mb, 300)
        self.assertEqual(first["t1"].threads, 7)
        _write_proc(self.root, 500, ticks=1000 + int(0.75 * 2 * tab_monitor.CLK_TCK))
        second = self.monitor.sample([("t1", None, True, False)], now=102.0)
        self.assertAlmostEqual(second["t1"].cpu, 0.75, places=2)
        self.assertEqual(second["t1"].verdict, "calm")  # over budget, but not for long

    def test_hot_after_ten_seconds_and_hog_after_a_minute(self):
        verdicts = []
        for now in (0.0, 2.0, 12.0, 30.0, 63.0):
            # a constant 90 % of one core between samples
            _write_proc(self.root, 501, ticks=int(0.9 * now * tab_monitor.CLK_TCK))
            verdicts.append(self.monitor.sample([("t1", None if self.monitor.pid_of("t1") else now, False, False)], now=now)["t1"].verdict)
        # first sample has no delta; over budget from t=2 on: hot at t>=12, hog at t>=62
        self.assertEqual(verdicts, ["calm", "calm", "hot", "hot", "hog"])

    def test_memory_alone_counts_as_over_budget(self):
        _write_proc(self.root, 502, ticks=0, rss_pages=1500 * self.mb_pages)
        self.monitor.sample([("t1", 0.0, False, True)], now=0.0)
        _write_proc(self.root, 502, ticks=0, rss_pages=1500 * self.mb_pages)
        sample = self.monitor.sample([("t1", None, False, True)], now=11.0)["t1"]
        self.assertEqual(sample.verdict, "hot")
        self.assertTrue(sample.audio)

    def test_going_calm_resets_the_clock(self):
        _write_proc(self.root, 503, ticks=0, rss_pages=2000 * self.mb_pages)
        self.monitor.sample([("t1", 0.0, False, False)], now=0.0)
        _write_proc(self.root, 503, ticks=0, rss_pages=100 * self.mb_pages)
        sample = self.monitor.sample([("t1", None, False, False)], now=30.0)["t1"]
        self.assertEqual(sample.verdict, "calm")
        self.assertIsNone(sample.over_since)

    def test_tabs_without_processes_are_harmless(self):
        result = self.monitor.sample([("t1", 0.0, True, False), ("t2", None, False, False)], now=0.0)
        self.assertEqual(result["t1"].cpu, 0.0)
        self.assertEqual(result["t1"].pid, 0)
        self.assertEqual(result["t2"].rss_mb, 0)
        self.assertEqual(self.monitor._last, {})

    def test_new_processes_are_paired_with_tabs_in_load_order_and_dropped_when_gone(self):
        _write_proc(self.root, 600, ticks=0)
        _write_proc(self.root, 601, ticks=0)
        # t_old started loading first, t_new later: the older process (lower pid) belongs to t_old
        self.monitor.sample([("t_new", 5.0, True, False), ("t_old", 1.0, False, False)], now=6.0)
        self.assertEqual(self.monitor.pid_of("t_old"), 600)
        self.assertEqual(self.monitor.pid_of("t_new"), 601)
        # a third tab that appears later gets the third process, existing pairs are kept
        _write_proc(self.root, 602, ticks=0)
        self.monitor.sample([("t_new", None, True, False), ("t_old", None, False, False), ("t3", 7.0, False, False)], now=8.0)
        self.assertEqual(self.monitor.pid_of("t3"), 602)
        self.assertEqual(self.monitor.pid_of("t_old"), 600)
        # the old tab's process dies (sleep/crash): the pairing is dropped, others stay
        import shutil
        shutil.rmtree(os.path.join(self.root, "600"))
        with open(os.path.join(self.root, "6000", "task", "6000", "children"), "w") as handle:
            handle.write("\n")
        self.monitor.sample([("t_new", None, True, False), ("t_old", None, False, False), ("t3", None, False, False)], now=10.0)
        self.assertEqual(self.monitor.pid_of("t_old"), 0)
        self.assertEqual(self.monitor.pid_of("t_new"), 601)

    def test_processes_alive_at_start_and_auxiliary_views_are_never_paired(self):
        _write_proc(self.root, 700, ticks=0)  # e.g. the keyboard panel, created before the monitor
        monitor = TabMonitor(proc=self.root, root_pid=1000)
        _write_proc(self.root, 701, ticks=0)  # the first tab
        monitor.sample([("t1", 1.0, True, False)], now=2.0)
        self.assertEqual(monitor.pid_of("t1"), 701)
        with monitor.auxiliary():
            _write_proc(self.root, 702, ticks=0)  # sidebar loads while a new tab is waiting
        _write_proc(self.root, 703, ticks=0)
        monitor.sample([("t1", None, True, False), ("t2", 3.0, False, False)], now=4.0)
        self.assertEqual(monitor.pid_of("t2"), 703)
        self.assertEqual(monitor._ignored, {700, 702})

    def test_real_process_tree_of_this_process(self):
        from core.tab_monitor import web_processes_under
        self.assertEqual(web_processes_under(os.getpid()), [])

    def test_describe_is_short_and_localised(self):
        sample = self.monitor.sample([], now=0.0)
        from core.tab_monitor import TabSample
        s = TabSample(tab_id="x", cpu=0.741, rss_mb=1229)
        self.assertEqual(describe(s), "CPU 74 % · 1,2 GB")
        self.assertEqual(describe(s, "en"), "CPU 74 % · 1.2 GB")
        self.assertEqual(describe(TabSample(tab_id="y", cpu=0.05, rss_mb=300)), "CPU 5 % · 300 MB")

    def test_real_proc_reading_of_this_process(self):
        monitor = TabMonitor()
        ticks, threads = monitor._read_stat(os.getpid())
        self.assertGreaterEqual(ticks, 0)
        self.assertGreater(threads, 0)
        self.assertGreater(monitor._read_rss_mb(os.getpid()), 1)


if __name__ == "__main__":
    unittest.main()
