"""Bounded recovery for interrupted search connections, with TLS validation intact."""
import html
import urllib.parse
from gi.repository import Gio, GLib
import gi
gi.require_version('WebKit2', '4.1')
from gi.repository import WebKit2


def can_retry_search(uri, method, error, attempted):
    # Only idempotent search GETs, never forms, account callbacks or certificates.
    parsed = urllib.parse.urlsplit(uri)
    return (not attempted and method == 'GET' and parsed.scheme == 'https'
            and parsed.hostname in ('duckduckgo.com', 'www.duckduckgo.com', 'html.duckduckgo.com', 'lite.duckduckgo.com')
            and parsed.path in ('', '/', '/html/', '/lite/')
            and bool(urllib.parse.parse_qs(parsed.query).get('q'))
            and any(error.matches(Gio.tls_error_quark(), code)
                    for code in (Gio.TlsError.EOF, Gio.TlsError.HANDSHAKE, Gio.TlsError.NOT_TLS)))


def error_html(uri, method, certificate=False):
    host = html.escape(urllib.parse.urlsplit(uri).hostname or '')
    target = html.escape(uri, quote=True)
    title = 'Varne povezave ni mogoče potrditi' if certificate else 'Strani trenutno ni mogoče odpreti'
    message = ('Spletno mesto je poslalo neveljavno potrdilo. Povezava je ostala blokirana.' if certificate
               else 'Povezava s spletnim mestom se je prekinila. Preverite povezavo in poskusite znova.')
    retry = f'<a href="{target}">Poskusi znova</a>' if method == 'GET' and not certificate else ''
    return f'''<!doctype html><html lang="sl"><meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
    <title>{title} — Safeer</title><style>html{{color-scheme:dark}}body{{background:#0c1420;color:#eef4fa;font:18px system-ui;max-width:620px;margin:12vh auto;padding:28px;line-height:1.6}}h1{{font-size:28px}}p{{color:#bdcadd}}a{{display:inline-block;padding:12px 22px;background:#85cd3e;color:#102006;border-radius:10px;text-decoration:none;font-weight:600}}</style>
    <h1>{title}</h1><p>{host}</p><p>{message}</p>{retry}<p>Za vrnitev uporabite gumb Nazaj ali Domov v brskalniku.</p></html>'''


class NetworkErrorHandler:
    def __init__(self, view):
        self.view = view
        self.requests = {}
        self.retried = set()
        self.error_document = False
        self.pending = None
        self.generation = 0
        view._safeer_load_failed = False
        view.connect('resource-load-started', self.resource_started)
        view.connect('load-changed', self.load_changed)
        view.connect('load-failed', self.load_failed)
        view.connect('load-failed-with-tls-errors', self.certificate_failed)
        view.connect('destroy', self.destroyed)

    def resource_started(self, view, resource, request):
        if resource == view.get_main_resource():
            self.requests = {request.get_uri(): request.get_http_method()}

    def load_changed(self, view, event):
        if event == WebKit2.LoadEvent.STARTED:
            self.generation += 1
        if event == WebKit2.LoadEvent.COMMITTED:
            if self.error_document:
                self.error_document = False
            else:
                view._safeer_load_failed = False
                self.retried.clear()

    def destroyed(self, *args):
        if self.pending:
            GLib.source_remove(self.pending)
            self.pending = None

    def show_error(self, uri, certificate=False):
        self.view._safeer_load_failed = True
        self.error_document = True
        self.view.load_alternate_html(error_html(uri, self.requests.get(uri), certificate), uri, None)

    def certificate_failed(self, view, uri, certificate, flags):
        self.show_error(uri, True)
        return True

    def load_failed(self, view, event, uri, error):
        if error.matches(WebKit2.network_error_quark(), WebKit2.NetworkError.CANCELLED):
            return False
        if error.matches(WebKit2.policy_error_quark(), WebKit2.PolicyError.FRAME_LOAD_INTERRUPTED_BY_POLICY_CHANGE):
            return False
        if can_retry_search(uri, self.requests.get(uri), error, uri in self.retried):
            self.retried.add(uri)
            generation = self.generation
            def retry():
                self.pending = None
                # A failed provisional navigation may restore the previous URI.
                # Guard against a newer navigation, rather than comparing that URI.
                if self.generation == generation:
                    view.load_uri(uri)
                return False
            self.pending = GLib.timeout_add(400, retry)
            return True
        certificate = error.matches(Gio.tls_error_quark(), Gio.TlsError.BAD_CERTIFICATE)
        self.show_error(uri, certificate)
        return True
