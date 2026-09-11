import json
import tempfile
import time
import unittest
from pathlib import Path

from core import adblock
from core.threat_intel import ThreatIntelService, _load_feed_module

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "signed_feed"
KEY = json.loads((FIXTURES / "public_key.json").read_text())
TRUSTED = {KEY["key_id"]: KEY["public_key"]}


class FixtureServer:
    def __init__(self):
        self.scenario = None
        self.offline = False
        self.requests = []

    def fetch(self, url, limit):
        self.requests.append(url)
        if self.offline:
            raise OSError("network unreachable")
        latest = FIXTURES / f"{self.scenario}-latest.json"
        if url.endswith("/v1/threats/latest.json"):
            data = latest.read_bytes()
        else:
            data = (FIXTURES / f"{self.scenario}-bundle.json").read_bytes()
        if len(data) > limit:
            raise ValueError("response too large")
        return data


class SignedThreatFeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = FixtureServer()

    def tearDown(self):
        self.tmp.cleanup()

    def service(self, trusted=TRUSTED, **kwargs):
        return ThreatIntelService(self.tmp.name, trusted_keys=trusted, base_urls=["https://intel.test"],
                                  fetch=self.server.fetch, **kwargs)

    def test_disabled_without_trusted_keys(self):
        service = self.service(trusted={})
        self.assertFalse(service.enabled)
        self.assertFalse(service.start())
        self.assertFalse(service.update_now())
        self.assertIsNone(service.match("https://malware.example/"))
        self.assertEqual(self.server.requests, [])

    def test_verified_update_blocks_every_indicator_type(self):
        service = self.service()
        self.server.scenario = "valid-100"
        self.assertTrue(service.update_now())
        self.assertEqual(service.status()["version"], 100)
        self.assertEqual(service.match("https://malware.example/login"), "malware")
        self.assertIsNone(service.match("https://sub.malware.example/"))
        self.assertEqual(service.match("https://a.phish.example/x"), "phishing")
        self.assertEqual(service.match("phish.example"), "phishing")
        self.assertEqual(service.match("http://files.example:8080/bin.sh"), "malware")
        self.assertIsNone(service.match("http://files.example:8080/other"))
        self.assertEqual(service.match("http://93.184.216.34/"), "botnet_c2")
        self.assertEqual(service.match("http://[2606:2800:220:1:248:1893:25c8:1946]/"), "botnet_c2")
        self.assertEqual(service.match("https://shop.xn--bcher-kva.example/"), "scam")
        self.assertIsNone(service.match("https://github.com/"))

    def test_every_failure_keeps_the_last_verified_bundle(self):
        service = self.service()
        self.server.scenario = "valid-100"
        self.assertTrue(service.update_now())
        for scenario in ("rollback-99", "forged-103", "expired-102", "tampered-104"):
            self.server.scenario = scenario
            self.assertFalse(service.update_now(), scenario)
            self.assertEqual(service.status()["version"], 100, scenario)
            self.assertEqual(service.match("https://malware.example/"), "malware", scenario)
            self.assertTrue(service.status()["last_error"], scenario)
        self.server.offline = True
        self.assertFalse(service.update_now())
        self.assertEqual(service.match("https://malware.example/"), "malware")

    def test_newer_bundle_replaces_rules_and_survives_restart(self):
        service = self.service()
        self.server.scenario = "valid-100"
        service.update_now()
        self.server.scenario = "valid-101"
        self.assertTrue(service.update_now())
        self.assertIsNone(service.match("https://malware.example/"))
        self.assertEqual(service.match("https://newbad.example/"), "malware")
        self.server.offline = True
        restarted = self.service()
        self.assertTrue(restarted.store.load())
        self.assertEqual(restarted.match("https://newbad.example/"), "malware")
        self.server.offline = False
        self.server.scenario = "valid-100"
        self.assertFalse(restarted.update_now())  # older than the stored version
        self.assertEqual(restarted.status()["version"], 101)

    def test_background_thread_updates_once_started(self):
        service = self.service(first_delay=0, interval=3600)
        self.server.scenario = "valid-100"
        self.assertTrue(service.start())
        deadline = time.time() + 10
        while service.status()["version"] != 100 and time.time() < deadline:
            time.sleep(0.05)
        service.stop()
        self.assertEqual(service.status()["version"], 100)

    def test_adblock_consults_registered_matcher_but_keeps_passthrough(self):
        service = self.service()
        self.server.scenario = "valid-100"
        service.update_now()
        adblock.register_threat_matcher(service.match)
        try:
            self.assertTrue(adblock.is_threat_domain("https://a.phish.example/"))
            self.assertTrue(adblock.is_threat_domain("https://payload-delivery.cc/"))  # built-in list still works
            self.assertFalse(adblock.is_threat_domain("https://clean.example/"))
            self.assertFalse(adblock.is_threat_domain("https://challenges.cloudflare.com/"))
        finally:
            adblock._extra_threat_matchers.remove(service.match)

    def test_pure_python_verifier_is_used_without_cryptography(self):
        feed = _load_feed_module()
        original = feed._Ed25519PublicKey
        feed._Ed25519PublicKey = None
        try:
            service = self.service()
            self.server.scenario = "valid-100"
            self.assertTrue(service.update_now())
            self.server.scenario = "forged-103"
            self.assertFalse(service.update_now())
        finally:
            feed._Ed25519PublicKey = original


if __name__ == "__main__":
    unittest.main()
