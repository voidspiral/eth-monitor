"""inet_diag / tcp_info parse fixtures (no live netlink)."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import struct
import unittest

from eth_monitor.sockdiag import parse_diag_dump

NLMSG_HDRLEN = 16
SOCK_DIAG_BY_FAMILY = 20
NLMSG_DONE = 3
INET_DIAG_MSG_LEN = 72
INET_DIAG_INFO = 2
TCP_INFO_BYTES_ACKED = 120
TCP_INFO_BYTES_RECEIVED = 128
TCP_INFO_BYTES_SENT = 200
AF_INET = 2
AF_INET6 = 10


def _align(n: int, to: int = 4) -> int:
    return (n + to - 1) & ~(to - 1)


def _nlmsg(nl_type: int, payload: bytes) -> bytes:
    length = NLMSG_HDRLEN + len(payload)
    hdr = struct.pack("IHHII", length, nl_type, 0, 0, 0)
    return hdr + payload


def _inet_diag_msg(inode: int, family: int) -> bytes:
    sockid = b"\x00" * 48
    rest = struct.pack("IIIII", 0, 0, 0, 0, inode)
    return bytes((family, 1, 0, 0)) + sockid + rest


def _rta(rta_type: int, data: bytes) -> bytes:
    rta_len = 4 + len(data)
    pad = b"\x00" * (_align(rta_len) - rta_len)
    return struct.pack("HH", rta_len, rta_type) + data + pad


def _tcp_info(*, acked: int, received: int, sent: int | None) -> bytes:
    size = 208 if sent is not None else 136
    buf = bytearray(size)
    struct.pack_into("<Q", buf, TCP_INFO_BYTES_ACKED, acked)
    struct.pack_into("<Q", buf, TCP_INFO_BYTES_RECEIVED, received)
    if sent is not None:
        struct.pack_into("<Q", buf, TCP_INFO_BYTES_SENT, sent)
    return bytes(buf)


def _sock_msg(
    inode: int,
    *,
    family: int = AF_INET,
    acked: int = 0,
    received: int = 0,
    sent: int | None = None,
) -> bytes:
    info = _tcp_info(acked=acked, received=received, sent=sent)
    payload = _inet_diag_msg(inode, family) + _rta(INET_DIAG_INFO, info)
    return _nlmsg(SOCK_DIAG_BY_FAMILY, payload)


class TestSockdiagParse(unittest.TestCase):
    def test_ipv4_uses_bytes_sent(self) -> None:
        blob = _sock_msg(11, received=100, acked=50, sent=80) + _nlmsg(NLMSG_DONE, b"")
        out = parse_diag_dump(blob)
        self.assertEqual(out[11].rx, 100)
        self.assertEqual(out[11].tx, 80)
        self.assertEqual(out[11].tx_field, "bytes_sent")
        self.assertFalse(out[11].partial)

    def test_ipv6_and_short_struct_fallback(self) -> None:
        blob = (
            _sock_msg(21, family=AF_INET6, received=10, acked=9, sent=8)
            + _sock_msg(22, received=40, acked=30, sent=None)
            + _nlmsg(NLMSG_DONE, b"")
        )
        out = parse_diag_dump(blob)
        self.assertEqual(out[21].rx, 10)
        self.assertEqual(out[21].tx, 8)
        self.assertFalse(out[21].partial)
        self.assertEqual(out[22].rx, 40)
        self.assertEqual(out[22].tx, 30)
        self.assertEqual(out[22].tx_field, "bytes_acked")
        self.assertTrue(out[22].partial)

    def test_empty_and_truncated_are_empty(self) -> None:
        self.assertEqual(parse_diag_dump(b""), {})
        self.assertEqual(parse_diag_dump(b"\x00\x01"), {})


if __name__ == "__main__":
    unittest.main()
