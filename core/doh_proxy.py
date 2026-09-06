#!/usr/bin/env python3
"""
Safeer Browser for Linux Mint - DNS-over-HTTPS (DoH) & Encrypted Proxy Engine
Encrypted DNS with HTTP/2 support and bounded local HTTP/CONNECT tunneling.
Public target lookups fail closed; resolver endpoint bootstrap uses the system DNS.
"""

import socket
import select
import threading
import time
import urllib.parse
import ipaddress
import math
import gi
gi.require_version("Soup", "3.0")
from gi.repository import Soup, Gio, GLib
from typing import Dict, Tuple, Optional, List

# Znani zanesljivi DoH ponudniki
DOH_PROVIDERS = {
    "quad9": {
        "name": "Quad9 Secure DNS (9.9.9.9)",
        "url": "https://dns.quad9.net/dns-query",
        "fallback_ip": "9.9.9.9"
    },
    "adguard": {
        "name": "AdGuard DNS (dns.adguard-dns.com)",
        "url": "https://dns.adguard-dns.com/dns-query",
        "fallback_ip": "94.140.14.14"
    },
    "cloudflare": {
        "name": "Cloudflare DNS (1.1.1.1)",
        "url": "https://1.1.1.1/dns-query",
        "fallback_ip": "1.1.1.1"
    },
    "google": {
        "name": "Google Public DNS (8.8.8.8)",
        "url": "https://dns.google/dns-query",
        "fallback_ip": "8.8.8.8"
    }
}


class DoHResolver:
    """
    Kriptografski razreševalnik DNS-over-HTTPS z lokalnim predpomnilnikom (In-Memory TTL Cache).
    Poizvedbe pošilja prek šifriranega TLS protokola neposredno na DoH strežnike.
    """

    def __init__(self, provider: str = "quad9", custom_url: str = ""):
        self.provider = provider if (provider in DOH_PROVIDERS or provider == "custom") else "quad9"
        self.custom_url = custom_url.strip()
        # Predpomnilnik: hostname -> (ip_address, expire_timestamp)
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._lock = threading.Lock()
        # SSL kontekst s preverjanjem veljavnosti sistemskih certifikatov
        self._transport = threading.local()
        self._pending = {}

    def set_provider(self, provider: str, custom_url: str = ""):
        with self._lock:
            c_url = custom_url.strip()
            if (provider in DOH_PROVIDERS or provider == "custom") and (provider != self.provider or c_url != self.custom_url):
                self.provider = provider
                self.custom_url = c_url
                self._cache.clear()

    def resolve(self, hostname: str, timeout: float = 3.5) -> Optional[str]:
        """
        Razreši domeno v IPv4 naslov prek DoH.
        Vrne IPv4 niz ali None, če poizvedba ne uspe.
        """
        if not hostname:
            return None

        h = hostname.lower().strip().rstrip(".")
        try:
            return str(ipaddress.ip_address(h))
        except ValueError:
            pass
        try:
            h = h.encode("idna").decode("ascii")
            if len(h) > 253 or any(not label or len(label) > 63 for label in h.split(".")):
                return None
        except UnicodeError:
            return None

        # Če je že IPv4 naslov
        parts = h.split(".")
        if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return h

        now = time.time()

        # 1. Preveri predpomnilnik
        with self._lock:
            cached = self._cache.get(h)
            if cached:
                ip, exp = cached
                if now < exp:
                    return ip
                else:
                    del self._cache[h]

        # Coalesce requests for one host and never fall back to plaintext DNS.
        with self._lock:
            generation = (self.provider, self.custom_url)
            key = (generation, h)
            event = self._pending.get(key)
            owner = event is None
            if owner:
                event = threading.Event()
                self._pending[key] = event
        if not owner:
            event.wait(timeout + 1)
            with self._lock:
                entry = self._cache.get(h)
                return entry[0] if entry and entry[1] > time.time() else None
        try:
            ip, ttl = self._query_doh(h, timeout)
            with self._lock:
                if generation == (self.provider, self.custom_url):
                    self._cache[h] = (ip, time.time() + (max(1, min(ttl, 3600)) if ip else 15))
            return ip
        finally:
            with self._lock:
                self._pending.pop(key, None)
                event.set()

    @staticmethod
    def _build_dns_wire_query(hostname: str) -> bytes:
        header = b"\x00\x01\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        qname = bytearray()
        for label in hostname.strip(".").split("."):
            l_bytes = label.encode("ascii", errors="ignore")
            qname.append(len(l_bytes))
            qname.extend(l_bytes)
        qname.append(0)
        return header + bytes(qname) + b"\x00\x01\x00\x01"

    @staticmethod
    def _parse_dns_wire_response(data: bytes) -> Tuple[Optional[str], int]:
        if len(data) < 12 or not data[2] & 0x80 or data[2] & 0x02 or data[3] & 0x0f:
            return None, 300
        try:
            qdcount = int.from_bytes(data[4:6], "big")
            ancount = int.from_bytes(data[6:8], "big")
            if ancount == 0:
                return None, 300

            idx = 12
            for _ in range(qdcount):
                while idx < len(data) and data[idx] != 0:
                    if data[idx] >= 192:
                        idx += 2
                        break
                    idx += 1 + data[idx]
                if idx < len(data) and data[idx] == 0:
                    idx += 1
                idx += 4

            for _ in range(ancount):
                if idx >= len(data):
                    break
                if data[idx] >= 192:
                    idx += 2
                else:
                    while idx < len(data) and data[idx] != 0:
                        idx += 1 + data[idx]
                    if idx < len(data) and data[idx] == 0:
                        idx += 1
                if idx + 10 > len(data):
                    break
                rtype = int.from_bytes(data[idx:idx+2], "big")
                ttl = int.from_bytes(data[idx+4:idx+8], "big")
                rdlength = int.from_bytes(data[idx+8:idx+10], "big")
                idx += 10
                if rtype == 1 and rdlength == 4 and idx + 4 <= len(data):
                    ip = f"{data[idx]}.{data[idx+1]}.{data[idx+2]}.{data[idx+3]}"
                    return ip, ttl
                idx += rdlength
        except Exception:
            pass
        return None, 300

    def _query_doh(self, hostname: str, timeout: float) -> Tuple[Optional[str], int]:
        if self.provider == "custom":
            base_url = self.custom_url
        else:
            provider_info = DOH_PROVIDERS.get(self.provider, DOH_PROVIDERS["quad9"])
            base_url = provider_info["url"]

        # libsoup 3 negotiates HTTP/2 (required by Quad9). It is already used by
        # WebKitGTK; keep normal certificate validation and bypass proxy recursion.
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None, 15
        try:
            session = getattr(self._transport, "session", None)
            if session is None:
                session = Soup.Session()
                session.set_proxy_resolver(Gio.SimpleProxyResolver.new(None, []))
                self._transport.session = session
            session.set_timeout(max(1, math.ceil(timeout)))
            message = Soup.Message.new("POST", base_url)
            message.set_flags(Soup.MessageFlags.NO_REDIRECT)
            message.set_request_body_from_bytes("application/dns-message", GLib.Bytes.new(self._build_dns_wire_query(hostname)))
            message.get_request_headers().append("Accept", "application/dns-message")
            stream = session.send(message, None)
            try:
                if message.get_status() != 200:
                    return None, 15
                if message.get_response_headers().get_content_type()[0] != "application/dns-message":
                    return None, 15
                data = bytearray()
                while len(data) <= 65535:
                    chunk = stream.read_bytes(min(8192, 65536 - len(data)), None).get_data()
                    if not chunk:
                        break
                    data.extend(chunk)
                if len(data) > 65535:
                    return None, 15
                return self._parse_dns_wire_response(bytes(data))
            finally:
                stream.close(None)
        except Exception:
            return None, 15


class LocalDoHProxy:
    """
    Visoko-zmogljiv lokalni posredniški strežnik (Loopback CONNECT Proxy).
    Prestreza omrežne zahteve brskalnika WebKit2 ter razrešuje vsa imena gostiteljev
    prek DoH brez puščanja DNS podatkov lokalnemu ponudniku interneta.
    """

    def __init__(self, resolver: DoHResolver, bind_host: str = "127.0.0.1", port: int = 0):
        self.resolver = resolver
        self.bind_host = bind_host
        self.requested_port = port
        self.actual_port = 0
        self.is_running = False
        self._server_sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._slots = threading.BoundedSemaphore(64)
        self._sockets = set()
        self._socket_lock = threading.Lock()

    def start(self) -> int:
        """Zažene posrednika v ločeni niti in vrne dodeljena lokalna vrata."""
        if self.is_running:
            return self.actual_port

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.bind_host, self.requested_port))
        self.actual_port = self._server_sock.getsockname()[1]
        self._server_sock.listen(128)
        self._server_sock.settimeout(1.0)

        self.is_running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True, name="SafeerDoHProxy")
        self._thread.start()

        print(f"[DoH Proxy] Lokalni posrednik aktiviran na http://{self.bind_host}:{self.actual_port} (DoH: {self.resolver.provider})")
        return self.actual_port

    def stop(self):
        """Varno ustavi posredniški strežnik."""
        self.is_running = False
        with self._socket_lock:
            for sock in list(self._sockets):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sock.close()
            self._sockets.clear()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

    def _accept_loop(self):
        while self.is_running:
            try:
                client_sock, _ = self._server_sock.accept()
                if not self._slots.acquire(blocking=False):
                    client_sock.close()
                    continue
                with self._socket_lock:
                    self._sockets.add(client_sock)
                t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                t.start()
            except Exception:
                if not self.is_running:
                    break

    def _handle_client(self, client_sock: socket.socket):
        remote_sock = None
        try:
            client_sock.settimeout(10.0)
            req_data = b""
            while b"\r\n\r\n" not in req_data and len(req_data) < 8192:
                chunk = client_sock.recv(2048)
                if not chunk:
                    break
                req_data += chunk

            if b"\r\n\r\n" not in req_data:
                client_sock.close()
                return

            headers, initial_body = req_data.split(b"\r\n\r\n", 1)
            header_line = req_data.split(b"\r\n", 1)[0].decode("latin1", errors="ignore")
            parts = header_line.split()
            if len(parts) < 2:
                client_sock.close()
                return

            method, target = parts[0].upper(), parts[1]

            if method == "CONNECT":
                # HTTPS Tunel: CONNECT example.com:443 HTTP/1.1
                if ":" in target:
                    host, port_s = target.rsplit(":", 1)
                    host = host.strip("[]")
                    port = int(port_s) if port_s.isdigit() else 443
                else:
                    host = target
                    port = 443

                resolved_ip = self.resolver.resolve(host)
                if not resolved_ip:
                    client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\nSafeer DoH: Razresevanje domene ni uspelo.")
                    client_sock.close()
                    return

                remote_sock = socket.create_connection((resolved_ip, port), timeout=10.0)
                with self._socket_lock:
                    self._sockets.add(remote_sock)
                if not self.is_running:
                    return

                # Potrdi tunel narocniku
                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

                # Odstrani timeoute za neomejen podatkovni prenos (streaming, web)
                client_sock.settimeout(30.0)
                remote_sock.settimeout(30.0)

                if initial_body:
                    remote_sock.sendall(initial_body)

                # Dvosmerno pretakanje bajtov med klientom in oddaljenim streznikom
                self._pipe_sockets(client_sock, remote_sock)

            elif method in ("GET", "POST", "HEAD", "PUT", "DELETE", "OPTIONS", "PATCH"):
                # Obicajni HTTP Proxy zahtevek
                parsed = urllib.parse.urlparse(target)
                host = parsed.hostname or ""
                port = parsed.port or 80

                resolved_ip = self.resolver.resolve(host)
                if not resolved_ip:
                    client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\nSafeer DoH: Razresevanje domene ni uspelo.")
                    client_sock.close()
                    return

                remote_sock = socket.create_connection((resolved_ip, port), timeout=10.0)
                with self._socket_lock:
                    self._sockets.add(remote_sock)
                if not self.is_running:
                    return

                # Preuredi zahtevek v relativno pot za ciljni streznik
                path = parsed.path or "/"
                if parsed.query:
                    path += f"?{parsed.query}"
                new_first_line = f"{method} {path} {parts[2] if len(parts) > 2 else 'HTTP/1.1'}\r\n".encode("latin1")
                rest_of_headers = b"\r\n".join(line for line in headers.split(b"\r\n")[1:]
                    if line.split(b":", 1)[0].lower() not in (b"proxy-authorization", b"proxy-connection")) + b"\r\n\r\n" + initial_body
                remote_sock.sendall(new_first_line + rest_of_headers)

                client_sock.settimeout(30.0)
                remote_sock.settimeout(30.0)
                self._pipe_sockets(client_sock, remote_sock)

            else:
                client_sock.close()

        except Exception:
            pass
        finally:
            with self._socket_lock:
                self._sockets.discard(client_sock)
                self._sockets.discard(remote_sock)
            self._slots.release()
            try:
                client_sock.close()
            except Exception:
                pass
            if remote_sock:
                try:
                    remote_sock.close()
                except Exception:
                    pass

    def _pipe_sockets(self, s1: socket.socket, s2: socket.socket):
        """Asinhrono dvosmerno posredovanje podatkov z nicelno zakasnitvijo."""
        sockets = [s1, s2]
        bufsize = 65536
        while self.is_running:
            try:
                readable, _, exceptional = select.select(sockets, [], sockets, 60.0)
                if exceptional:
                    break
                if not readable:
                    break

                for s in readable:
                    data = s.recv(bufsize)
                    if not data:
                        return
                    target = s2 if s is s1 else s1
                    target.sendall(data)
            except Exception:
                break


# Globalni primerek posrednika za enojni vir resnice (Single Source of Truth)
_global_resolver: Optional[DoHResolver] = None
_global_proxy: Optional[LocalDoHProxy] = None
_proxy_lock = threading.Lock()


def get_doh_proxy(provider: str = "quad9", custom_url: str = "", enabled: bool = True) -> Optional[LocalDoHProxy]:
    """Pridobi ali inicializira globalni primerek DoH posrednika."""
    global _global_resolver, _global_proxy
    with _proxy_lock:
        if not enabled:
            if _global_proxy:
                _global_proxy.stop()
                _global_proxy = None
            return None

        if _global_resolver is None:
            _global_resolver = DoHResolver(provider, custom_url)
        else:
            _global_resolver.set_provider(provider, custom_url)

        if _global_proxy is None:
            _global_proxy = LocalDoHProxy(_global_resolver)
            _global_proxy.start()

        return _global_proxy
