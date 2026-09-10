import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.adblock import YOUTUBE_KEEP_WATCHING_SCRIPT

ROOT = Path(__file__).resolve().parents[1]


class YouTubeKeepWatchingTests(unittest.TestCase):
    def test_script_is_limited_to_youtube_and_handles_idle_prompts(self):
        script = YOUTUBE_KEEP_WATCHING_SCRIPT
        self.assertIn("host === 'youtube.com'", script)
        self.assertIn("window._lact = Date.now()", script)
        for renderer in ("ytmusic-you-there-renderer", "ytd-you-there-renderer", "yt-confirm-dialog-renderer"):
            self.assertIn(renderer, script)

    def test_every_tab_injects_the_script_into_youtube_top_frames(self):
        source = (ROOT / "safeer_mint.py").read_text()
        block = re.search(r"add_script\(WebKit2\.UserScript\(\s*YOUTUBE_KEEP_WATCHING_SCRIPT,(.*?)\)\)", source, re.S)
        self.assertIsNotNone(block)
        self.assertIn("TOP_FRAME", block.group(1))
        self.assertIn('"*://*.youtube.com/*"', block.group(1))

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_script_is_valid_javascript(self):
        with tempfile.NamedTemporaryFile("w", suffix=".js") as handle:
            handle.write(YOUTUBE_KEEP_WATCHING_SCRIPT)
            handle.flush()
            subprocess.run(["node", "--check", handle.name], check=True)
