import unittest
from types import SimpleNamespace
from core.adblock import strip_tracking_parameters


class LoginNavigationTests(unittest.TestCase):
    def test_native_verification_frame_is_allowed_but_script_urls_are_not(self):
        from safeer_mint import is_safe_web_url
        self.assertTrue(is_safe_web_url('about:srcdoc'))
        self.assertTrue(is_safe_web_url('about:blank'))
        for url in ['javascript:alert(1)', 'data:text/html,hello', 'file:///etc/passwd']:
            self.assertFalse(is_safe_web_url(url))

    def test_auth_and_signed_links_remain_exact(self):
        for suffix in ['return_to=%2F%3Fq%3DreasoningMode%3Dnone%26voice%3Dfalse', 'state=a%20b&code=c%2Fd', 'secret=dummy&si=needed',
                       'SAMLResponse=x%2By&RelayState=z', 'X-Amz-Signature=dummy',
                       'token=dummy', 'redirect_uri=https%3A%2F%2Fexample.org']:
            url='https://example.org/cb?utm_source=mail&'+suffix
            self.assertEqual(strip_tracking_parameters(url), url)
        url='https://example.org/login?utm_source=mail&next=a%20b'
        self.assertEqual(strip_tracking_parameters(url),url)

    def test_ordinary_tracking_removed_without_reencoding(self):
        self.assertEqual(strip_tracking_parameters('https://example.org/article?x=a%20b&x=%2f&utm_source=mail&empty#part'),
                         'https://example.org/article?x=a%20b&x=%2f&empty#part')

    def test_post_and_redirect_navigation_are_never_replayed(self):
        from safeer_mint import SafeerMintBrowser, WebKit2
        for method, redirect, kind in [('POST',False,WebKit2.NavigationType.FORM_SUBMITTED),
                                       ('GET',True,WebKit2.NavigationType.OTHER)]:
            calls=[]
            uri='https://example.org/submit?utm_source=mail'
            req=SimpleNamespace(get_uri=lambda:uri,get_http_method=lambda:method)
            nav=SimpleNamespace(get_request=lambda:req,get_navigation_type=lambda:kind,
                                is_redirect=lambda:redirect,get_mouse_button=lambda:0,get_modifiers=lambda:0)
            decision=SimpleNamespace(get_navigation_action=lambda:nav,use=lambda:calls.append('use'),ignore=lambda:calls.append('ignore'))
            app=SimpleNamespace(config={},is_download_url=lambda u:False)
            view=SimpleNamespace(load_uri=lambda u:calls.append('replay'))
            SafeerMintBrowser.on_decide_policy(app,view,decision,WebKit2.PolicyDecisionType.NAVIGATION_ACTION)
            self.assertEqual(calls,['use'])

    def test_popup_policy_leaves_request_to_webkit_and_blocks_threats(self):
        from safeer_mint import SafeerMintBrowser, WebKit2
        for uri, expected in [('https://example.org/auth?state=dummy','use'),
                              ('https://payload-delivery.cc/oauth/authorize','ignore'),
                              ('https://tpc.googlesyndication.com/ad','ignore')]:
            calls=[]
            req=SimpleNamespace(get_uri=lambda:uri)
            nav=SimpleNamespace(get_request=lambda:req)
            decision=SimpleNamespace(get_navigation_action=lambda:nav,use=lambda:calls.append('use'),ignore=lambda:calls.append('ignore'))
            config=SimpleNamespace(get=lambda key,default=None:default,increment_ads_blocked=lambda n:None,increment_threats_blocked=lambda n:None)
            app=SimpleNamespace(config=config,is_download_url=lambda u:False,show_threat_warning=lambda u:None)
            SafeerMintBrowser.on_decide_policy(app,None,decision,WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION)
            self.assertEqual(calls,[expected])

    def test_auth_exclusions_include_cloudflare_and_xai(self):
        from core.adblock import AUTH_SCRIPT_EXCLUSIONS
        required = [
            "*://x.ai/*",
            "*://*.x.ai/*",
            "*://challenges.cloudflare.com/*",
            "*://*.cloudflare.com/*",
            "*://static.cloudflareinsights.com/*",
            "*://*.turnstile.com/*",
        ]
        for pattern in required:
            self.assertIn(pattern, AUTH_SCRIPT_EXCLUSIONS)

    def test_cloudflare_and_xai_passthrough(self):
        from core.adblock import is_passthrough_host, is_ad_domain, is_threat_domain, strip_tracking_parameters
        hosts = [
            "https://accounts.x.ai/check-login?redirect=grok-com&state=123",
            "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/jsd",
            "https://grok.com/",
            "https://static.cloudflareinsights.com/beacon.min.js",
        ]
        for url in hosts:
            self.assertTrue(is_passthrough_host(url))
            self.assertFalse(is_ad_domain(url))
            self.assertFalse(is_threat_domain(url))
            self.assertEqual(strip_tracking_parameters(url), url)
