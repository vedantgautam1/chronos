"""Environment checks for the v2 project.

The v2 environment must run Python 3.14 (V2-D45), import its own package
(``chronos2``), and stay fully separate from the frozen v1 ``chronos`` package.
One further check proves the CI Postgres service answers a query, so B09
inherits a working service.
"""

import importlib.util
import os
import socket
import struct
import sys
from urllib.parse import urlparse

import pytest


def test_python_is_314():
    assert sys.version_info[:2] == (3, 14)


def test_import_chronos2():
    import chronos2

    assert chronos2.__name__ == "chronos2"


def test_v1_chronos_is_not_importable():
    assert importlib.util.find_spec("chronos") is None


# --- minimal Postgres client (stdlib only) ---------------------------------
# B01 adds no Postgres driver (psycopg arrives in B09), so the SELECT 1 test
# speaks the wire protocol directly. It supports only the ``trust`` auth used
# by the CI service and the local test Postgres.


def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Postgres closed the connection early")
        buf += chunk
    return buf


def _read_message(sock: socket.socket) -> tuple[bytes, bytes]:
    typ = sock.recv(1)
    if not typ:
        raise ConnectionError("Postgres closed the connection")
    (length,) = struct.unpack("!I", _read_exact(sock, 4))
    return typ, _read_exact(sock, length - 4)


def _postgres_select_1(dsn: str) -> str:
    parsed = urlparse(dsn)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    db = (parsed.path or "/postgres").lstrip("/") or "postgres"

    with socket.create_connection((host, port), timeout=10) as sock:
        body = (
            b"user\x00"
            + user.encode()
            + b"\x00"
            + b"database\x00"
            + db.encode()
            + b"\x00\x00"
        )
        sock.sendall(struct.pack("!II", 4 + 4 + len(body), 196608) + body)

        while True:
            typ, payload = _read_message(sock)
            if typ == b"R":  # AuthenticationRequest
                (code,) = struct.unpack("!I", payload[:4])
                if code != 0:
                    raise ConnectionError(
                        f"Postgres requested unsupported auth (code {code}); use trust auth"
                    )
            elif typ == b"E":  # ErrorResponse
                raise ConnectionError(
                    "Postgres startup error: " + payload.decode(errors="replace")
                )
            elif typ == b"Z":  # ReadyForQuery
                break

        query = b"SELECT 1\x00"
        sock.sendall(b"Q" + struct.pack("!I", 4 + len(query)) + query)

        value: str | None = None
        while True:
            typ, payload = _read_message(sock)
            if typ == b"D":  # DataRow
                (ncols,) = struct.unpack("!h", payload[:2])
                off = 2
                vals = []
                for _ in range(ncols):
                    (length,) = struct.unpack("!i", payload[off : off + 4])
                    off += 4
                    vals.append(payload[off : off + length].decode())
                    off += length
                value = vals[0]
            elif typ == b"E":
                raise ConnectionError("Postgres error: " + payload.decode(errors="replace"))
            elif typ == b"Z":
                break
        return value


def test_postgres_select_1():
    dsn = os.environ.get(
        "CHRONOS2_TEST_DSN", "postgresql://postgres@localhost:5432/postgres"
    )
    try:
        assert _postgres_select_1(dsn) == "1"
    except (ConnectionError, OSError) as exc:
        pytest.fail(
            f"Postgres is not reachable at {dsn} ({exc}). Start it "
            "(CI: the postgres:16 service; cloud: pg_ctlcluster 16 main start; "
            "Mac: the handbook §5) and set CHRONOS2_TEST_DSN."
        )
