"""Live check of the overload protection on a real desktop, in an isolated profile (1.0.24).

Starts a second Safeer instance from this checkout (XDG_CONFIG_HOME in a temp dir, so a running
browser, its socket and settings are untouched), opens a heavy synthetic page whose Web Worker burns
a core (workers are not throttled in hidden tabs, like a feed's media/JS), then a light page as the
active tab (the heavy one goes to the background), and verifies from the outside: safeer.log has the
memory-limit line and no CRITICAL about thresholds, the monitor logs the hot tab, the background tab
is put to sleep after the patience period. Then the instance is closed.

Run on a graphical session:  PYTHONPATH=. python3 -m unittest -v tests.live_obremenitev
Writes tests/live-obremenitev-report.json. Takes about two minutes.

Observed 2026-09-13 on Linux Mint 22.3 / WebKitGTK 2.52.6: monitor active at +7 s, tab over budget
(CPU 98 %, 181 MB) logged at +26 s, "dolgo nad proračunom (v ozadju)" and "uspavan" at +72 s; the
heavy process was gone from the process list at the next sample.
"""
import json
import os
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "tests", "live-obremenitev-report.json")

HEAVY = """<!doctype html><html><head><meta charset="utf-8"><title>Težka stran (test)</title></head>
<body><h1>Težka stran</h1><p id="n">0</p>
<script>
var code = 'var n = 0; function spin() { var t = Date.now(); while (Date.now() - t < 200) { n++; } postMessage(n); setTimeout(spin, 0); } spin();';
var w = new Worker(URL.createObjectURL(new Blob([code], {type: 'application/javascript'})));
w.onmessage = function (e) { document.getElementById('n').textContent = e.data; };
</script></body></html>"""
LIGHT = "<!doctype html><html><head><meta charset='utf-8'><title>Lahka stran (test)</title></head><body><p>ok</p></body></html>"


def _has_display():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or os.path.exists(f"/run/user/{os.getuid()}/wayland-0"))


@unittest.skipUnless(_has_display(), "needs a graphical session")
class LiveOverload(unittest.TestCase):
    def test_overload_protection(self):
        report = {"started": time.strftime("%Y-%m-%d %H:%M:%S")}
        tmp = tempfile.mkdtemp(prefix="safeer-live-")
        with open(os.path.join(tmp, "heavy.html"), "w") as h:
            h.write(HEAVY)
        with open(os.path.join(tmp, "light.html"), "w") as h:
            h.write(LIGHT)
        server = subprocess.Popen(["python3", "-m", "http.server", "18765", "--bind", "127.0.0.1"], cwd=tmp,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        env = dict(os.environ)
        env["XDG_CONFIG_HOME"] = os.path.join(tmp, "config")
        env.setdefault("DISPLAY", ":0")
        env.setdefault("WAYLAND_DISPLAY", "wayland-0")
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        env["SAFEER_NO_SCOPE"] = "1"
        log_dir = os.path.join(tmp, "config", "safeer-mint")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "settings.json"), "w") as h:
            # no first-run wizard and no default-browser bar: both are modal / interactive
            json.dump({"first_run_completed": True, "check_default_browser": False, "doh_enabled": False}, h)
        stderr_path = os.path.join(tmp, "stderr.txt")
        stderr_file = open(stderr_path, "w")
        proc = subprocess.Popen(["python3", os.path.join(ROOT, "safeer_mint.py"), "http://127.0.0.1:18765/heavy.html"],
                                cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=stderr_file)
        log = ""
        try:
            time.sleep(8)
            report["running"] = proc.poll() is None
            sock = os.path.join(log_dir, "safeer.sock")
            report["socket"] = os.path.exists(sock)
            if os.path.exists(sock):
                import socket as _s
                c = _s.socket(_s.AF_UNIX, _s.SOCK_STREAM)
                c.connect(sock)
                c.sendall(b"OPEN http://127.0.0.1:18765/light.html")
                try:
                    c.recv(64)
                except Exception:
                    pass
                c.close()
            samples = []
            t0 = time.time()
            slept = False
            while time.time() - t0 < 100:
                time.sleep(5)
                try:
                    with open(os.path.join(log_dir, "safeer.log"), encoding="utf-8") as h:
                        log = h.read()
                except FileNotFoundError:
                    log = ""
                top = subprocess.run("ps -o pcpu=,args= -C WebKitWebProcess --sort=-pcpu | head -1 | cut -c1-40", shell=True,
                                     capture_output=True, text=True).stdout.strip()
                samples.append({"t": round(time.time() - t0), "top_webproc": top, "hot": "nad proračunom" in log, "slept": "uspavan" in log})
                if "uspavan" in log:
                    slept = True
                    break
                if proc.poll() is not None:
                    break
            report["samples"] = samples[-6:]
            report["log_tail"] = [l for l in log.splitlines() if " W " not in l][-20:]
            report["memory_line"] = next((l for l in log.splitlines() if "Meja na zavihek" in l), "")
            report["monitor_line"] = next((l for l in log.splitlines() if "Nadzor zavihkov aktiven" in l), "")
            report["hot_seen"] = "nad proračunom" in log
            report["slept"] = slept
            report["still_running"] = proc.poll() is None
            report["exit_code"] = proc.poll()
        finally:
            try:
                proc.send_signal(signal.SIGTERM)
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
            server.terminate()
            stderr_file.close()
            try:
                with open(stderr_path, encoding="utf-8", errors="replace") as h:
                    err = h.read().splitlines()
                report["stderr_tail"] = [l for l in err if "Deprecat" not in l and not l.startswith("  ") and l.strip()][-12:]
                report["threshold_critical"] = any("conservative_threshold" in l for l in err)
            except Exception:
                pass
            with open(REPORT, "w", encoding="utf-8") as h:
                json.dump(report, h, indent=1, ensure_ascii=False)
        print(json.dumps(report, indent=1, ensure_ascii=False))
        self.assertTrue(report.get("running"), "Safeer se ni zagnal")
        self.assertTrue(report.get("memory_line"), "ni vrstice o meji pomnilnika v safeer.log")
        self.assertFalse(report.get("threshold_critical"), "WebKit je zavrnil prage pomnilnika")
        self.assertTrue(report.get("monitor_line"), "nadzor zavihkov se ni oglasil")
        self.assertTrue(report.get("hot_seen"), "nadzor ni zaznal težkega zavihka")
        self.assertTrue(report.get("slept"), "težek zavihek v ozadju ni zaspal")
        self.assertTrue(report.get("still_running"), "Safeer se je med testom končal")
