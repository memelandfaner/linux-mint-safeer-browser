"""AppStream opis mora prestati preverjanje, sicer pade gradnja AppImage.

13. 9. 2026: opis izdaje 1.0.26 je vseboval golo spletno pot (»https://«), appstreamcli je
javil description-has-plaintext-url, linuxdeploy pa je gradnjo ustavil z izhodno kodo 1.
Preverjanje je bilo pred tem samo v CI — deset minut na napako, ki jo vidimo tu v hipu.
"""
import re
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "io.github.memelandfaner.SafeerBrowser.metainfo.xml"


class MetainfoTests(unittest.TestCase):
    def test_release_descriptions_contain_no_plain_urls(self):
        drevo = ET.parse(META)
        izdaje = drevo.getroot().find("releases")
        self.assertIsNotNone(izdaje, "v metainfo ni izdaj")
        for izdaja in izdaje:
            besedilo = "".join(izdaja.itertext())
            najdba = re.search(r"\b(https?://|www\.)", besedilo)
            self.assertIsNone(
                najdba,
                f"izdaja {izdaja.get('version')} ima golo spletno pot: "
                f"{najdba.group(0) if najdba else ''}")

    def test_every_release_has_a_version_and_a_date(self):
        drevo = ET.parse(META)
        for izdaja in drevo.getroot().find("releases"):
            self.assertTrue(izdaja.get("version"), "izdaja brez razlicice")
            self.assertRegex(izdaja.get("date", ""), r"^\d{4}-\d{2}-\d{2}$")

    def test_the_newest_release_matches_the_packaged_version(self):
        razlicica = (ROOT / "packaging" / "VERSION").read_text(encoding="utf-8").strip()
        drevo = ET.parse(META)
        prva = list(drevo.getroot().find("releases"))[0]
        self.assertEqual(prva.get("version"), razlicica,
                         "najnovejsa izdaja v metainfo se ne ujema s packaging/VERSION")

    def test_appstreamcli_finds_no_errors_when_it_is_available(self):
        """Lovimo napake, ne razlik med razlicicami orodja.

        Starejsi appstreamcli na gradilniku javi 'unknown-tag developer' in
        'url-invalid-type vcs-browser' — to je v datoteki ze od prej in gradnje ne ustavi.
        Izhodna koda je zato neuporabna; pomembne so napake (E:) in opozorilo o goli
        spletni poti, ki je 13. 9. 2026 ustavilo gradnjo AppImage.
        """
        orodje = shutil.which("appstreamcli")
        if not orodje:
            self.skipTest("appstreamcli ni nameščen")
        izid = subprocess.run([orodje, "validate", "--no-net", str(META)],
                              capture_output=True, text=True)
        izpis = izid.stdout + izid.stderr
        napake = [v.strip() for v in izpis.splitlines() if v.strip().startswith("E:")]
        self.assertEqual(napake, [], "appstreamcli javlja napake:\n" + "\n".join(napake))
        self.assertNotIn("description-has-plaintext-url", izpis,
                         "gola spletna pot v opisu ustavi gradnjo AppImage")


if __name__ == "__main__":
    unittest.main()
