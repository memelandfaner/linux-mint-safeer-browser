import concurrent.futures
import socket
import threading
import time
import unittest
from unittest.mock import patch
from core.doh_proxy import DoHResolver, LocalDoHProxy

class NetworkTests(unittest.TestCase):
    def test_failed_dns_is_coalesced_cached_and_never_plaintext(self):
        resolver = DoHResolver()
        calls=[]
        def fail(*args):
            calls.append(1); time.sleep(.08); return None,15
        with patch.object(resolver,'_query_doh',side_effect=fail), patch('socket.getaddrinfo',side_effect=AssertionError('DNS leak')):
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                self.assertEqual(list(pool.map(resolver.resolve,['missing.invalid']*12)),[None]*12)
            self.assertIsNone(resolver.resolve('missing.invalid'))
        self.assertEqual(len(calls),1)
        resolver.set_provider('quad9')
        self.assertFalse(resolver._cache)

    def test_invalid_custom_endpoint(self):
        resolver=DoHResolver('custom','http://example.test/dns-query')
        self.assertEqual(resolver._query_doh('example.com',1),(None,15))

    def test_proxy_preserves_coalesced_connect_payload_and_stop(self):
        server=socket.socket(); server.bind(('127.0.0.1',0)); server.listen(64)
        stopped=threading.Event()
        def echo(c):
            with c:
                while True:
                    try: data=c.recv(65536)
                    except OSError: return
                    if not data: return
                    try: c.sendall(data)
                    except OSError: return
        def accept():
            while not stopped.is_set():
                try: c,_=server.accept()
                except OSError: return
                threading.Thread(target=echo,args=(c,),daemon=True).start()
        threading.Thread(target=accept,daemon=True).start()
        proxy=LocalDoHProxy(DoHResolver()); port=proxy.start()
        payload=b'coalesced TLS bytes\x00\xff'*100
        def check(_):
            with socket.create_connection(('127.0.0.1',port),timeout=4) as c:
                c.sendall(('CONNECT 127.0.0.1:%d HTTP/1.1\r\nHost: local\r\n\r\n'%server.getsockname()[1]).encode()+payload)
                data=b''
                while b'\r\n\r\n' not in data: data+=c.recv(65536)
                head,body=data.split(b'\r\n\r\n',1)
                self.assertIn(b'200',head)
                while len(body)<len(payload): body+=c.recv(65536)
                self.assertEqual(body,payload)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool: list(pool.map(check,range(40)))
            c=socket.create_connection(('127.0.0.1',port),timeout=4)
            c.sendall(('CONNECT 127.0.0.1:%d HTTP/1.1\r\n\r\n'%server.getsockname()[1]).encode())
            self.assertIn(b'200',c.recv(1024)); proxy.stop(); self.assertEqual(c.recv(1024),b''); c.close()
        finally: proxy.stop(); stopped.set(); server.close()

    def test_http_post_retains_body_and_removes_proxy_credentials(self):
        server=socket.socket();server.bind(('127.0.0.1',0));server.listen(1)
        received=[]
        def read():
            c,_=server.accept()
            with c:
                data=b''
                while not data.endswith(b'hello'): data+=c.recv(4096)
                received.append(data); c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK')
        t=threading.Thread(target=read,daemon=True);t.start()
        proxy=LocalDoHProxy(DoHResolver()); port=proxy.start()
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=4) as c:
                c.sendall(('POST http://127.0.0.1:%d/path?q=1 HTTP/1.1\r\nHost: local\r\nContent-Length: 5\r\nProxy-Authorization: secret\r\n\r\nhello'%server.getsockname()[1]).encode())
                self.assertIn(b'200',c.recv(4096))
            t.join(3);self.assertTrue(received[0].startswith(b'POST /path?q=1 HTTP/1.1'))
            self.assertNotIn(b'secret',received[0]);self.assertTrue(received[0].endswith(b'hello'))
        finally: proxy.stop();server.close()

if __name__=='__main__': unittest.main()
