#!/usr/bin/env python3
"""Private, loopback-only HTTP/TLS fixtures for disposable guest tests.

Prints ports.json once ready. Stop with SIGINT/SIGTERM. Generated keys stay in
ignored test output and must never be distributed or trusted outside the lab.
"""
import argparse
import datetime as dt
import ipaddress
import json
from pathlib import Path
import signal
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    out.chmod(0o700)
    valid_start, valid_end = dt.datetime(1970, 1, 1), dt.datetime(2035, 1, 1)

    def certificate(label, issuer=None, wrong=False, expired=False):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, label)])
        builder = (x509.CertificateBuilder().subject_name(name)
                   .issuer_name(issuer[0].subject if issuer else name)
                   .public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(dt.datetime(1951, 1, 1) if expired else valid_start)
                   .not_valid_after(dt.datetime(1952, 1, 1) if expired else valid_end)
                   .add_extension(x509.BasicConstraints(ca=issuer is None, path_length=None), True))
        if issuer:
            names = [x509.DNSName('wrong.invalid')] if wrong else [
                x509.DNSName('fixture.test'), x509.IPAddress(ipaddress.ip_address('10.0.2.2')),
                x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
                x509.IPAddress(ipaddress.ip_address('::1'))]
            builder = builder.add_extension(x509.SubjectAlternativeName(names), False)
        cert = builder.sign(issuer[1] if issuer else key, hashes.SHA256())
        (out / (label + '.crt')).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        target = out / (label + '.key')
        target.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                          serialization.PrivateFormat.TraditionalOpenSSL,
                          serialization.NoEncryption()))
        target.chmod(0o600)
        return cert, key

    ca = certificate('ca')
    foreign = certificate('foreign-ca')
    certificate('valid', ca)
    certificate('wrong-host', ca, wrong=True)
    certificate('expired', ca, expired=True)
    certificate('untrusted', foreign)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *args):
            pass
        def do_GET(self):
            record = {'endpoint': self.server.fixture_name, 'path': self.path,
                      'tls': self.connection.version() if isinstance(self.connection, ssl.SSLSocket) else None}
            with lock:
                with (out / 'requests.jsonl').open('a') as log:
                    log.write(json.dumps(record) + '\n')
            path = self.path.split('?', 1)[0]
            if path in ['/redirect', '/loop']:
                self.send_response(302)
                self.send_header('Location', '/ok' if path == '/redirect' else '/loop')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if path == '/large':
                self.send_response(200)
                self.send_header('Transfer-Encoding', 'chunked')
                self.end_headers()
                data = bytes(65 + i % 26 for i in range(131072))
                for offset in range(0, len(data), 4096):
                    chunk = data[offset:offset+4096]
                    self.wfile.write(('%x\r\n' % len(chunk)).encode() + chunk + b'\r\n')
                self.wfile.write(b'0\r\n\r\n')
                return
            if path in ['/page', '/second', '/secure']:
                title = {'/page': 'Network browser check', '/second': 'Second page', '/secure': 'Secure browser check'}[path]
                data = ('<html><head><title>' + title + '</title></head><body><h1>' + title +
                        '</h1><p id="js">pending</p><script>document.getElementById("js").textContent="JavaScript works";</script></body></html>').encode()
            else:
                data = b'fixture-ok\n' if path == '/ok' else b'not-found\n'
            self.send_response(404 if path == '/missing' else 200)
            self.send_header('Content-Type', 'text/html' if path in ['/page','/second','/secure'] else 'text/plain')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    servers = []
    ports = {}
    for name, cert, protocol in [('http', None, None), ('tls12', 'valid', ssl.TLSVersion.TLSv1_2),
                                 ('tls13', 'valid', ssl.TLSVersion.TLSv1_3),
                                 ('wrong-host', 'wrong-host', None), ('expired', 'expired', None),
                                 ('untrusted', 'untrusted', None)]:
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        server.fixture_name = name
        if cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            if protocol:
                context.minimum_version = context.maximum_version = protocol
            context.load_cert_chain(out / (cert + '.crt'), out / (cert + '.key'))
            server.socket = context.wrap_socket(server.socket, server_side=True)
        servers.append(server)
        ports[name] = server.server_port
        threading.Thread(target=server.serve_forever, daemon=True).start()
    (out / 'ports.json').write_text(json.dumps(ports, indent=2) + '\n')
    print(out / 'ports.json', flush=True)
    stop = threading.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda *_: stop.set())
    try:
        stop.wait()
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
