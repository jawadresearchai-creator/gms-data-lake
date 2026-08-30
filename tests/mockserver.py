"""A tiny HTTP server that reproduces every failure mode the real sources
exhibit, so the engine's handling of them is testable offline."""
from __future__ import annotations

import http.server
import threading


class Handler(http.server.BaseHTTPRequestHandler):
    hits: dict[str, int] = {}

    def log_message(self, *a):  # silence
        pass

    def _count(self):
        Handler.hits[self.path] = Handler.hits.get(self.path, 0) + 1

    def do_HEAD(self):
        self.do_GET(head_only=True)

    def do_GET(self, head_only: bool = False):  # noqa: C901
        self._count()
        p = self.path

        if p.startswith("/ok.csv"):
            body = b"a,b,c\n1,2,3\n" * 50
            etag = '"v1"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", etag)
            self.send_header("Last-Modified", "Wed, 21 Oct 2026 07:28:00 GMT")
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
            return

        if p.startswith("/htmlpage"):
            # A 200 that is actually a web page: the FDIC / consent-wall case.
            body = b"<!DOCTYPE html><html><head><title>Search</title></head><body>no data</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
            return

        if p.startswith("/forbidden"):
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if p.startswith("/gone"):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if p.startswith("/huge"):
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(50 * 1024 * 1024))
            self.end_headers()
            if not head_only:
                self.wfile.write(b"\0" * 1024)
            return

        if p.startswith("/flaky"):
            # 503 on the first two hits, then succeed: exercises backoff.
            n = Handler.hits.get(p, 0)
            if n <= 2:
                self.send_response(503)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = b"recovered\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
            return

        if p.startswith("/empty"):
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()


class MockServer:
    def __init__(self):
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self):
        Handler.hits.clear()
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
