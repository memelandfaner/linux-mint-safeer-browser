import unittest
from gi.repository import Gio, GLib
from core.network_errors import can_retry_search, error_html

class NetworkErrorTests(unittest.TestCase):
    def test_only_first_safe_search_get_retries(self):
        error = GLib.Error.new_literal(Gio.tls_error_quark(), 'Peer closed connection', Gio.TlsError.EOF)
        url='https://duckduckgo.com/?q=test'
        self.assertTrue(can_retry_search(url,'GET',error,False))
        reported=GLib.Error.new_literal(Gio.tls_error_quark(),'The TLS connection was non-properly terminated',Gio.TlsError.NOT_TLS)
        self.assertTrue(can_retry_search(url,'GET',reported,False))
        self.assertFalse(can_retry_search(url,'POST',error,False))
        self.assertFalse(can_retry_search(url,'GET',error,True))
        self.assertFalse(can_retry_search('https://duckduckgo.com/login?q=test','GET',error,False))
        badcert=GLib.Error.new_literal(Gio.tls_error_quark(),'Bad certificate',Gio.TlsError.BAD_CERTIFICATE)
        self.assertFalse(can_retry_search(url,'GET',badcert,False))
    def test_error_page_does_not_replay_forms_or_allow_certificates(self):
        self.assertNotIn('href=',error_html('https://example.org/','POST'))
        self.assertNotIn('href=',error_html('https://example.org/','GET',True))
        self.assertIn('&quot;',error_html('https://example.org/?q="test"','GET'))
        self.assertNotIn('<script>',error_html('https://example.org/','GET'))

    def test_recovery_keeps_previous_uri_and_does_not_override_new_navigation(self):
        from unittest.mock import patch
        from core.network_errors import NetworkErrorHandler, WebKit2
        class View:
            def __init__(self): self.loaded=[]
            def connect(self,*args): pass
            def load_uri(self,uri): self.loaded.append(uri)
            def get_uri(self): return 'about:blank'
        url='https://duckduckgo.com/?q=test'
        error=GLib.Error.new_literal(Gio.tls_error_quark(),'EOF',Gio.TlsError.NOT_TLS)
        v=View();h=NetworkErrorHandler(v);h.requests[url]='GET';callbacks=[]
        with patch('core.network_errors.GLib.timeout_add',side_effect=lambda delay,cb: callbacks.append(cb) or 1):
            self.assertTrue(h.load_failed(v,WebKit2.LoadEvent.STARTED,url,error))
        callbacks.pop()();self.assertEqual(v.loaded,[url])
        h.retried.clear()
        with patch('core.network_errors.GLib.timeout_add',side_effect=lambda delay,cb: callbacks.append(cb) or 1):
            h.load_failed(v,WebKit2.LoadEvent.STARTED,url,error)
        h.load_changed(v,WebKit2.LoadEvent.STARTED)
        callbacks.pop()();self.assertEqual(v.loaded,[url])
