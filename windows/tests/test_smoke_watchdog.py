import unittest
from pathlib import Path

SMOKE = Path(__file__).resolve().parents[1] / "safeer_windows" / "smoke.py"
BROWSER = Path(__file__).resolve().parents[1] / "safeer_windows" / "browser.py"


class SmokeWatchdogTests(unittest.TestCase):
    """A hung event loop used to end as a bare subprocess timeout with no report to look at."""

    def setUp(self):
        self.source = SMOKE.read_text(encoding="utf-8")

    def test_hung_run_writes_a_report_and_stops_the_process(self):
        start = self.source.index("def arm_hard_watchdog(")
        block = self.source[start:self.source.index("timer.start()", start)]
        self.assertIn("threading.Timer", self.source[start:])
        self.assertIn('"failed": ["hung"]', block)
        self.assertIn('"stage": STAGE', block)
        self.assertIn("os._exit(3)", block)
        self.assertLess(block.index("json.dump(payload"), block.index("os._exit(3)"))

    def test_a_startup_exception_ends_in_the_report(self):
        browser = BROWSER.read_text(encoding="utf-8")
        block = browser[browser.index("def smoke_main("):]
        self.assertIn("except BaseException", block)
        self.assertIn("report_crash(args.report, traceback.format_exc())", block)
        for inside in ("apply_dns_mode(settings)", "SafeerBrowserApp(qt_app", "qt_app.exec()"):
            self.assertLess(block.index("try:"), block.index(inside), inside)
        crash = self.source[self.source.index("def report_crash("):self.source.index("def stage(")]
        self.assertIn('"failed": ["crash"]', crash)
        self.assertIn('"traceback": text', crash)

    def test_the_watchdog_is_armed_before_anything_that_can_block(self):
        browser = BROWSER.read_text(encoding="utf-8")
        start = browser.index("def smoke_main(")
        block = browser[start:]
        self.assertIn("arm_hard_watchdog(args.report", block)
        for later in ("apply_dns_mode(settings)", "SafeerBrowserApp(qt_app", "qt_app.exec()"):
            self.assertLess(block.index("arm_hard_watchdog"), block.index(later), later)

    def test_stacks_are_dumped_even_when_the_gil_is_held(self):
        block = self.source[self.source.index("def arm_stack_dump("):self.source.index("def stage(")]
        self.assertIn("faulthandler.dump_traceback_later", block)
        self.assertIn("repeat=True", block)
        self.assertIn("stacks_path(report)", block)
        armed = self.source[self.source.index("def arm_hard_watchdog("):self.source.index("def give_up(")]
        self.assertIn("arm_stack_dump(report", armed)
        workflow = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "windows-package.yml").read_text()
        self.assertIn("build/windows/out/*.log", workflow)  # the dump has to reach the artifacts

    def test_progress_is_written_next_to_the_report(self):
        self.assertIn("-progress.json", self.source)
        block = self.source[self.source.index("def stage("):self.source.index("def arm_hard_watchdog(")]
        self.assertIn("json.dump({\"stage\": name", block)
        self.assertIn("except OSError", block)  # a windowed build has no console to fall back on

    def test_every_stage_and_check_is_logged(self):
        self.assertIn('stage("local server")', self.source)
        self.assertIn('stage("profile")', self.source)
        self.assertIn('stage("scenario")', self.source)
        self.assertIn("stage(f\"check {name}", self.source)


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
