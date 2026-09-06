import unittest
from core.adblock import is_threat_domain,is_ad_domain
class ThreatTests(unittest.TestCase):
 def test_advertising_is_not_reported_as_botnet(self):
  u='https://tpc.googlesyndication.com/sodar/5k7CCto5.html'
  self.assertTrue(is_ad_domain(u));self.assertFalse(is_threat_domain(u))
 def test_threats_remain_blocked_with_video_paths(self):
  self.assertTrue(is_threat_domain('https://payload-delivery.cc/embed/video.m3u8'))
  self.assertFalse(is_ad_domain('https://payload-delivery.cc/embed/video.m3u8'))
 def test_domain_boundaries(self):
  for u in ['https://github.com','https://youtube.com','https://notgooglesyndication.com','https://googlesyndication.com.example.org']:
   self.assertFalse(is_ad_domain(u));self.assertFalse(is_threat_domain(u))

class NavigationTests(unittest.TestCase):
 def test_ad_frame_is_ignored_without_a_threat_dialog(self):
  from types import SimpleNamespace
  from safeer_mint import SafeerMintBrowser, WebKit2
  counts=[]; ignored=[]
  config=SimpleNamespace(get=lambda key,default=None:default,increment_ads_blocked=lambda n:counts.append(n))
  def warning(*args): raise AssertionError('Ad frame opened a malware warning')
  app=SimpleNamespace(config=config,show_threat_warning=warning)
  request=SimpleNamespace(get_uri=lambda:'https://tpc.googlesyndication.com/sodar/5k7CCto5.html')
  nav=SimpleNamespace(get_request=lambda:request)
  decision=SimpleNamespace(get_navigation_action=lambda:nav,ignore=lambda:ignored.append(True))
  self.assertTrue(SafeerMintBrowser.on_decide_policy(app,None,decision,WebKit2.PolicyDecisionType.NAVIGATION_ACTION))
  self.assertEqual(ignored,[True]);self.assertEqual(counts,[1])
