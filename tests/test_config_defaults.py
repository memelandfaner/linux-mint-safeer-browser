import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from core import config

class DefaultBookmarksTests(unittest.TestCase):
    def setup_profile(self, initial=None):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        path=Path(self.temp.name)/'settings.json'
        if initial is not None:path.write_text(json.dumps(initial))
        p1=patch.object(config,'CONFIG_DIR',self.temp.name);p2=patch.object(config,'CONFIG_FILE',str(path))
        p1.start();p2.start();self.addCleanup(p1.stop);self.addCleanup(p2.stop)
        return path
    def test_fresh_and_deleted_bookmarks_stay_empty(self):
        self.setup_profile()
        manager=config.ConfigManager();self.assertEqual(manager.get_portals(),[])
        manager.add_portal('Mine','https://example.org')
        manager.save_portals([])
        self.assertEqual(config.ConfigManager().get_portals(),[])
    def test_migration_preserves_custom_and_modified_bookmarks(self):
        custom={'id':'mine','title':'My page','url':'https://example.org'}
        edited={**config.LEGACY_DEFAULT_PORTALS[0],'title':'My videos'}
        self.setup_profile({'custom_portals':copy.deepcopy(config.LEGACY_DEFAULT_PORTALS)+[custom,edited]})
        manager=config.ConfigManager()
        self.assertEqual([p['title'] for p in manager.get_portals()],['My page','My videos'])
        self.assertTrue(manager.get('default_bookmarks_removed'))
    def test_user_can_readd_former_default_after_migration(self):
        self.setup_profile({'default_bookmarks_removed':True,'custom_portals':copy.deepcopy(config.LEGACY_DEFAULT_PORTALS[:1])})
        self.assertEqual(len(config.ConfigManager().get_portals()),1)
