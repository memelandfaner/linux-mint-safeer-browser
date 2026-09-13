"""Per-tab memory limit and the browser's own log file (1.0.24)."""
import importlib
import io
import os
import sys
import tempfile
import unittest


def _source():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "safeer_mint.py"), encoding="utf-8") as handle:
        return handle.read()


class MemoryLimitTests(unittest.TestCase):
    def _limit(self):
        # safeer_mint imports GTK at module level; read the function without importing the module.
        source = _source()
        start = source.index("def web_process_memory_limit_mb(")
        end = source.index("def start_threat_intel():")
        namespace = {"os": os}
        exec(source[start:end], namespace)  # noqa: S102 - our own source
        return namespace["web_process_memory_limit_mb"]

    def test_limit_is_half_of_ram_and_at_least_one_gb(self):
        limit = self._limit()
        self.assertEqual(limit(12 * 1024), 6144)
        self.assertEqual(limit(8 * 1024), 4096)
        self.assertEqual(limit(4 * 1024), 2048)
        self.assertEqual(limit(1024), 1024)
        self.assertEqual(limit(64 * 1024), 32768)

    def test_memory_pressure_settings_get_an_explicit_limit(self):
        source = _source()
        block = source[source.index("mps = WebKit2.MemoryPressureSettings()"):source.index("set_memory_pressure_settings(mps)")]
        self.assertIn("mps.set_memory_limit(limit_mb)", block)
        self.assertIn("set_kill_threshold(1.0)", block)
        # WebKit asserts conservative < strict on each setter call: strict must be raised first.
        self.assertLess(block.index("set_strict_threshold(0.75)"), block.index("set_conservative_threshold(0.5)"))
        self.assertIn("exceeded-memory-limit", source)


class LogFileTests(unittest.TestCase):
    def test_print_lines_land_in_the_rotating_log_and_still_reach_the_terminal(self):
        from core import log
        importlib.reload(log)
        original_out, original_err = sys.stdout, sys.stderr
        captured = io.StringIO()
        sys.__stdout__ = captured  # what the launcher's terminal (or /dev/null) would receive
        try:
            with tempfile.TemporaryDirectory() as config_dir:
                path = log.install(config_dir, "9.9.9")
                print("[Test] hello from stdout")
                print("[Test] warning on stderr", file=sys.stderr)
                sys.stdout.flush()
                with open(path, encoding="utf-8") as handle:
                    content = handle.read()
                self.assertIn("Safeer Browser 9.9.9 started", content)
                self.assertIn("I [Test] hello from stdout", content)
                self.assertIn("W [Test] warning on stderr", content)
                self.assertIn("hello from stdout", captured.getvalue())
                # Installing twice is harmless.
                self.assertEqual(log.install(config_dir), path)
        finally:
            sys.stdout, sys.stderr = original_out, original_err
            sys.__stdout__ = original_out
            for handler in list(__import__("logging").getLogger("safeer").handlers):
                __import__("logging").getLogger("safeer").removeHandler(handler)
                handler.close()


if __name__ == "__main__":
    unittest.main()


class TabLoadIntegrationTests(unittest.TestCase):
    """Source-level checks of how the browser wires the monitor (GTK cannot be imported here)."""

    def test_monitor_runs_from_the_main_loop_and_tabs_get_an_indicator(self):
        source = _source()
        self.assertIn("GLib.timeout_add_seconds(2, self._monitor_tabs)", source)
        self.assertIn('"load_btn": btn_load', source)
        self.assertIn('tab.get("load_started_at")', source)

    def test_sleeping_tab_is_not_reported_as_a_crash_and_reloads_on_selection(self):
        source = _source()
        handler = source[source.index("def on_web_process_terminated"):source.index("def on_web_process_terminated") + 400]
        self.assertIn('tab.get("sleeping")', handler)
        sleep = source[source.index("def sleep_tab"):source.index("def show_tab_load_menu")]
        self.assertIn('tab["deferred"] = True', sleep)
        self.assertIn("terminate_web_process()", sleep)
        started = source[source.index("def on_tab_load_changed"):source.index("def on_tab_title_changed")]
        self.assertIn('item["sleeping"] = False', started)

    def test_only_background_tabs_without_sound_are_put_to_sleep_and_it_can_be_switched_off(self):
        source = _source()
        tick = source[source.index("def _monitor_tabs"):source.index("def sleep_tab")]
        self.assertIn('sample.verdict == "hog" and not sample.active and not sample.audio', tick)
        self.assertIn('self.config.get("sleep_heavy_background_tabs", True)', tick)
        from core import config
        self.assertTrue(config.DEFAULT_SETTINGS.get("sleep_heavy_background_tabs"))

    def test_closing_a_tab_forgets_it_in_the_monitor(self):
        source = _source()
        close = source[source.index("def close_tab"):source.index("def close_tab") + 1800]
        self.assertIn("self.tab_monitor.forget(tab_id)", close)


class LauncherScopeTests(unittest.TestCase):
    def test_launcher_runs_the_browser_in_a_user_scope_when_available(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "packaging", "safeer-launcher"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("systemd-run --user --scope", text)
        self.assertIn("MemoryHigh=60%", text)
        self.assertIn("SAFEER_NO_SCOPE", text)          # opt-out and recursion guard
        self.assertIn("-- true >/dev/null 2>&1; then", text)  # probed first, silently skipped elsewhere
