import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from gi.repository import GLib
from core import default_browser as default


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
        key=GLib.KeyFile();key.load_from_data(repaired,len(repaired.encode()),GLib.KeyFileFlags.NONE)
        self.assertEqual(set(key.get_string_list('Desktop Entry','MimeType')),set(default.WEB_TYPES))
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
