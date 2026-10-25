"""Test doubles shared by the smoke-test unit tests (stdlib only)."""

import json
import socket
import threading


class FakeServer:
    """Fake debug server: accepts connections, reads one line, answers one line.

    `reply` is a dict sent for every request, or a callable(request) -> dict.
    Every decoded request is appended to `seen`.
    """

    def __init__(self, reply):
        self.reply = reply
        self.seen = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self._stop = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        self.sock.settimeout(0.2)
        while not self._stop:
            try:
                conn, _ = self.sock.accept()
            except (socket.timeout, OSError):
                continue
            with conn:
                buf = b""
                conn.settimeout(2.0)
                try:
                    while not buf.endswith(b"\n"):
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                except socket.timeout:
                    pass
                request = json.loads(buf.decode()) if buf.strip() else {}
                if request:
                    self.seen.append(request)
                reply = self.reply(request) if callable(self.reply) else self.reply
                conn.sendall((json.dumps(reply) + "\n").encode())

    def close(self):
        self._stop = True
        self.sock.close()
        self.thread.join(timeout=2)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _FakeProc:
    """Stand-in for subprocess.Popen: poll() returns the given exit code (None = running)."""

    def __init__(self, exit_code):
        self.returncode = exit_code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9
