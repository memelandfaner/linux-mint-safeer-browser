import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from gi.repository import GLib
from core import default_browser as default

ROOT=Path(__file__).resolve().parents[1]


class DefaultBrowserTests(unittest.TestCase):
    def test_misplaced_mime_type_is_repaired_without_changing_actions(self):
        original='''[Desktop Entry]
Type=Application
Name=Safeer
Name[sl]=Moj brskalnik
Exec=/usr/bin/true %U
Actions=NewWindow;

[Desktop Action NewWindow]
Name=Novo okno
Exec=/usr/bin/true
MimeType=text/html;
'''
        repaired=default.desktop_entry_text(original,'/tmp')
        self.assertEqual(default.desktop_entry_text(repaired,'/tmp'),repaired)
        # KEEP_TRANSLATIONS: without it GLib drops Name[sl] unless the runner locale is Slovenian.
        key=GLib.KeyFile();key.load_from_data(repaired,len(repaired.encode()),GLib.KeyFileFlags.KEEP_TRANSLATIONS)
        self.assertEqual(set(key.get_string_list('Desktop Entry','MimeType')),set(default.WEB_TYPES))
        self.assertIn('Name[sl]=Moj brskalnik',repaired)
        self.assertEqual(key.get_string('Desktop Entry','Name[sl]'),'Moj brskalnik')
        self.assertEqual(key.get_string('Desktop Action NewWindow','Exec'),'/usr/bin/true')
        self.assertNotIn('MimeType',key.get_keys('Desktop Action NewWindow')[0])

    def test_partial_or_similarly_named_default_is_not_success(self):
        app=lambda name:SimpleNamespace(get_id=lambda:name)
        with patch.object(default.Gio.AppInfo,'get_default_for_type',side_effect=[app(default.DESKTOP_ID),app('other-safeer.desktop')]):
            self.assertFalse(default.is_default_browser())
        with patch.object(default.Gio.AppInfo,'get_default_for_type',return_value=None):
            self.assertFalse(default.is_default_browser())

    def test_native_registration_in_isolated_xdg_profile(self):
        with tempfile.TemporaryDirectory(prefix='safeer-default-test-') as temp:
            root=Path(temp);apps=root/'data'/'applications';apps.mkdir(parents=True)
            (root/'config').mkdir()
            (apps/default.DESKTOP_ID).write_text('[Desktop Entry]\nType=Application\nName=Safeer\nExec=/usr/bin/true %U\n[Desktop Action NewWindow]\nName=New\nExec=/usr/bin/true\nMimeType=text/html;\n')
            (apps/'other.desktop').write_text('[Desktop Entry]\nType=Application\nName=Other\nExec=/usr/bin/true %U\nMimeType=application/pdf;\n')
            (root/'config'/'mimeapps.list').write_text('[Default Applications]\napplication/pdf=other.desktop;\n')
            env=dict(os.environ,XDG_DATA_HOME=str(root/'data'),XDG_CONFIG_HOME=str(root/'config'),
                     XDG_DATA_DIRS=str(root/'system'),XDG_CONFIG_DIRS=str(root/'system-config'))
            script='''
from pathlib import Path
from gi.repository import Gio
from core.default_browser import set_default_browser,is_default_browser,WEB_TYPES,DESKTOP_ID
assert not is_default_browser()
for _ in range(2):
 success,errors=set_default_browser(Path.cwd())
 assert success,errors
 assert is_default_browser()
 for t in WEB_TYPES: assert Gio.AppInfo.get_default_for_type(t,False).get_id()==DESKTOP_ID
assert Gio.AppInfo.get_default_for_type('application/pdf',False).get_id()=='other.desktop'
app=Gio.DesktopAppInfo.new(DESKTOP_ID)
assert set(WEB_TYPES).issubset(app.get_supported_types())
print('Native defaults verified; unrelated PDF preference preserved')
'''
            subprocess.run(['/usr/bin/python3','-c',script],env=env,check=True,capture_output=True,text=True)


class StaleEntryTests(unittest.TestCase):
    """Matej, 2026-09-13: the per-user safeer-browser.desktop still pointed at the removed
    ~/.local/bin/safeer-browser; GLib refused to load it, the click raised TypeError and the
    question bar never went away."""

    def test_exec_of_a_removed_launcher_is_replaced_and_the_entry_loads(self):
        with tempfile.TemporaryDirectory(prefix='safeer-stale-') as temp:
            app_dir=Path(temp)/'lib'/'safeer-browser';app_dir.mkdir(parents=True)
            (app_dir/'safeer_mint.py').write_text('#')
            stale=('[Desktop Entry]\nType=Application\nName=Safeer Browser\nExec=/nonexistent/safeer-browser %U\n'
                   'Actions=NewWindow;\n\n[Desktop Action NewWindow]\nName=New Window\nExec=/nonexistent/safeer-browser\n')
            repaired=default.desktop_entry_text(stale,str(app_dir))
            key=GLib.KeyFile();key.load_from_data(repaired,len(repaired.encode()),GLib.KeyFileFlags.NONE)
            self.assertIn('safeer_mint.py',key.get_string('Desktop Entry','Exec'))
            self.assertTrue(key.get_string('Desktop Entry','Exec').endswith(' %U'))
            self.assertIn('safeer_mint.py',key.get_string('Desktop Action NewWindow','Exec'))
            path=Path(temp)/'safeer-browser.desktop';path.write_text(repaired)
            self.assertIsNotNone(default.Gio.DesktopAppInfo.new_from_filename(str(path)))

    def test_packaged_launcher_is_preferred_and_a_foreign_checkout_is_replaced(self):
        with tempfile.TemporaryDirectory(prefix='safeer-pkg-') as temp:
            root=Path(temp);(root/'bin').mkdir();(root/'lib'/'safeer-browser').mkdir(parents=True)
            launcher=root/'bin'/'safeer';launcher.write_text('#!/bin/sh\n');launcher.chmod(0o755)
            (root/'lib'/'safeer-browser'/'safeer_mint.py').write_text('#')
            other=root/'other'/'safeer_mint.py';other.parent.mkdir();other.write_text('#')
            self.assertEqual(default.launcher_command(root/'lib'/'safeer-browser'),f'"{launcher}"')
            self.assertTrue(default._starts_this_install(f'"{launcher}" %U',root/'lib'/'safeer-browser'))
            self.assertTrue(default._starts_this_install(f'/usr/bin/python3 "{root}/lib/safeer-browser/safeer_mint.py" %U',root/'lib'/'safeer-browser'))
            self.assertFalse(default._starts_this_install(f'/usr/bin/python3 "{other}" %U',root/'lib'/'safeer-browser'))
            text=default.desktop_entry_text(f'[Desktop Entry]\nType=Application\nName=Safeer\nExec=/usr/bin/python3 "{other}" %U\n',root/'lib'/'safeer-browser')
            self.assertIn(f'Exec="{launcher}" %U',text)

    def test_stale_user_entry_is_retired_when_a_packaged_entry_exists(self):
        with tempfile.TemporaryDirectory(prefix='safeer-retire-') as temp:
            root=Path(temp);user=root/'data'/'applications';system=root/'system'/'applications'
            user.mkdir(parents=True);system.mkdir(parents=True)
            (root/'bin').mkdir();(root/'lib'/'safeer-browser').mkdir(parents=True)
            launcher=root/'bin'/'safeer';launcher.write_text('#!/bin/sh\n');launcher.chmod(0o755)
            (root/'lib'/'safeer-browser'/'safeer_mint.py').write_text('#')
            (system/default.DESKTOP_ID).write_text(f'[Desktop Entry]\nType=Application\nName=Safeer Browser\nExec={launcher} %U\n')
            (user/default.DESKTOP_ID).write_text('[Desktop Entry]\nType=Application\nName=Safeer Browser\nExec=/nonexistent/safeer-browser %U\n')
            with patch.object(default.GLib,'get_user_data_dir',return_value=str(root/'data')), \
                 patch.object(default.GLib,'get_system_data_dirs',return_value=[str(root/'system')]):
                chosen=default.ensure_desktop_entry(root/'lib'/'safeer-browser')
            self.assertEqual(chosen,system/default.DESKTOP_ID)
            self.assertFalse((user/default.DESKTOP_ID).exists())
            self.assertTrue((user/'safeer-browser.desktop.safeer-backup').exists())

    def test_exec_arguments_are_quoted_only_when_the_spec_requires_it(self):
        # xdg-utils take the first word of Exec literally, so a plain path must stay unquoted.
        self.assertEqual(default._exec_argument('/usr/bin/safeer'),'/usr/bin/safeer')
        self.assertEqual(default._exec_argument('/home/x/Neimenovana mapa/safeer_mint.py'),'"/home/x/Neimenovana mapa/safeer_mint.py"')
        self.assertEqual(default._exec_argument('/tmp/50%/a'),'"/tmp/50%%/a"')
        with tempfile.TemporaryDirectory(prefix='safeer-plain-') as temp:
            root=Path(temp);(root/'bin').mkdir();(root/'lib'/'safeer-browser').mkdir(parents=True)
            launcher=root/'bin'/'safeer';launcher.write_text('#!/bin/sh\n');launcher.chmod(0o755)
            self.assertEqual(default.launcher_command(root/'lib'/'safeer-browser'),str(launcher))

    def test_deb_desktop_entry_uses_an_absolute_launcher(self):
        text=(ROOT/'build_deb.sh').read_text()
        self.assertIn("s|^Exec=safeer|Exec=/usr/bin/safeer|",text)
