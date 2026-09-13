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

    def test_limit_is_a_quarter_of_ram_within_bounds(self):
        limit = self._limit()
        self.assertEqual(limit(12 * 1024), 2048)
        self.assertEqual(limit(8 * 1024), 2048)
        self.assertEqual(limit(4 * 1024), 1024)
        self.assertEqual(limit(2 * 1024), 768)
        self.assertEqual(limit(64 * 1024), 2048)

    def test_memory_pressure_settings_get_an_explicit_limit(self):
        source = _source()
        block = source[source.index("mps = WebKit2.MemoryPressureSettings()"):source.index("set_memory_pressure_settings(mps)")]
        self.assertIn("mps.set_memory_limit(limit_mb)", block)
        self.assertIn("set_kill_threshold(1.0)", block)
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
