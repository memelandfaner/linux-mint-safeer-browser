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
        # Activity must stay current without timers (throttled in hidden/minimized windows).
        self.assertIn("Object.defineProperty(window, '_lact'", script)
        self.assertIn("get: function () { return Date.now(); }", script)
        self.assertIn("'yt-popup-opened'", script)
        # A background tab is not laid out, so the confirmation must not look at element sizes.
        self.assertNotIn("getBoundingClientRect", script)
        self.assertIn("ytmusic-button-renderer button", script)
        self.assertIn("Promise.resolve().then(scan)", script)
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


def _chromium_path():
    import os
    path = os.environ.get("SAFEER_CHROMIUM", "")
    return path if path and os.path.exists(path) else ""


@unittest.skipUnless(_chromium_path(), "set SAFEER_CHROMIUM to a Chromium binary to run the browser test")
class YouTubeKeepWatchingBrowserTests(unittest.TestCase):
    def test_prompt_resumes_the_player_video_and_ignores_hover_previews(self):
        from playwright.sync_api import sync_playwright

        page_html = """<!doctype html><html><body>
<div id="movie_player"><video id="main"></video></div>
<ytd-rich-item-renderer><video id="preview"></video></ytd-rich-item-renderer>
<script>
window.played = [];
for (const v of document.querySelectorAll('video')) {
  Object.defineProperty(v, 'paused', { value: true, configurable: true });
  v.play = function () { window.played.push(this.id); return Promise.resolve(); };
}
</script></body></html>"""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=_chromium_path(), args=["--no-sandbox"])
            try:
                context = browser.new_context()
                context.route("https://www.youtube.com/**", lambda route: route.fulfill(
                    status=200, content_type="text/html", body=page_html))
                context.add_init_script(YOUTUBE_KEEP_WATCHING_SCRIPT)
                page = context.new_page()
                page.goto("https://www.youtube.com/watch?v=fixture")
                page.wait_for_timeout(100)
                page.evaluate("""() => {
                    window.addPrompt = (tag, css) => {
                        const prompt = document.createElement(tag);
                        prompt.style.cssText = css;
                        const button = document.createElement('button');
                        button.textContent = 'Yes';
                        button.onclick = () => { window.confirmed = (window.confirmed || 0) + 1; };
                        prompt.appendChild(button);
                        document.body.appendChild(prompt);
                        return prompt;
                    };
                    document.getElementById('main').dispatchEvent(new Event('pause'));
                    // A hover preview that pauses by itself afterwards must not take over.
                    document.getElementById('preview').dispatchEvent(new Event('pause'));
                    // Zero size is what a tab in the background reports; the prompt is still up.
                    window.addPrompt('ytmusic-you-there-renderer', 'display:block;width:0;height:0');
                }""")
                page.wait_for_function("window.confirmed >= 1 && window.played.length >= 1", timeout=5000)
                page.wait_for_timeout(600)
                played = page.evaluate("window.played")
                self.assertIn("main", played)
                self.assertNotIn("preview", played)
                # A prompt that is really hidden must be left alone.
                page.evaluate("window.confirmed = 0; window.addPrompt('ytd-you-there-renderer', 'display:none')")
                page.wait_for_timeout(1500)
                self.assertEqual(page.evaluate("window.confirmed"), 0)
            finally:
                browser.close()
