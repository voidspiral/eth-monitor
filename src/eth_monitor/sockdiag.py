"""Parse INET_DIAG / tcp_info byte counters (stdlib netlink)."""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass

NETLINK_SOCK_DIAG = 4
SOCK_DIAG_BY_FAMILY = 20
NLMSG_DONE = 3
NLMSG_ERROR = 2
NLM_F_REQUEST = 1
NLM_F_DUMP = 0x300
NLMSG_HDRLEN = 16
INET_DIAG_MSG_LEN = 72
INET_DIAG_INFO = 2
INET_DIAG_NOCOOKIE = 0xFFFFFFFF
IPPROTO_TCP = 6
TCP_INFO_BYTES_ACKED = 120
TCP_INFO_BYTES_RECEIVED = 128
TCP_INFO_BYTES_SENT = 200
TCP_INFO_RX_MIN = 136
TCP_INFO_SENT_MIN = 208
TX_FIELD_SENT = "bytes_sent"
TX_FIELD_ACKED = "bytes_acked"


@dataclass(frozen=True)
class TcpBytes:
    rx: int
    tx: int
    tx_field: str
    partial: bool


def _align(n: int, to: int = 4) -> int:
    return (n + to - 1) & ~(to - 1)


def _parse_tcp_info(info: bytes) -> TcpBytes | None:
    if len(info) < TCP_INFO_RX_MIN:
        return None
    rx = struct.unpack_from("<Q", info, TCP_INFO_BYTES_RECEIVED)[0]
    if len(info) >= TCP_INFO_SENT_MIN:
        tx = struct.unpack_from("<Q", info, TCP_INFO_BYTES_SENT)[0]
        return TcpBytes(rx=rx, tx=tx, tx_field=TX_FIELD_SENT, partial=False)
    acked = struct.unpack_from("<Q", info, TCP_INFO_BYTES_ACKED)[0]
    return TcpBytes(rx=rx, tx=acked, tx_field=TX_FIELD_ACKED, partial=True)


def _parse_attrs(blob: bytes) -> bytes | None:
    offset = 0
    info: bytes | None = None
    while offset + 4 <= len(blob):
        rta_len, rta_type = struct.unpack_from("HH", blob, offset)
        if rta_len < 4 or offset + rta_len > len(blob):
            break
        payload = blob[offset + 4 : offset + rta_len]
        if rta_type == INET_DIAG_INFO:
            info = payload
        offset += _align(rta_len)
    return info


def parse_diag_dump(data: bytes) -> dict[int, TcpBytes]:
    out: dict[int, TcpBytes] = {}
    offset = 0
    while offset + NLMSG_HDRLEN <= len(data):
        nl_len, nl_type, _flags, _seq, _pid = struct.unpack_from("IHHII", data, offset)
        if nl_len < NLMSG_HDRLEN:
            break
        next_off = offset + _align(nl_len)
        if offset + nl_len > len(data):
            break
        if nl_type in {NLMSG_DONE, NLMSG_ERROR}:
            break
        payload = data[offset + NLMSG_HDRLEN : offset + nl_len]
        if len(payload) >= INET_DIAG_MSG_LEN:
            inode = struct.unpack_from("I", payload, INET_DIAG_MSG_LEN - 4)[0]
            info = _parse_attrs(payload[INET_DIAG_MSG_LEN:])
            parsed = _parse_tcp_info(info) if info is not None else None
            if parsed is not None and inode:
                out[inode] = parsed
        offset = next_off
    return out


def _diag_request(family: int) -> bytes:
    ext = 1 << (INET_DIAG_INFO - 1)
    sockid = (
        struct.pack("HH", 0, 0)
        + b"\x00" * 32
        + struct.pack("I", 0)
        + struct.pack("II", INET_DIAG_NOCOOKIE, INET_DIAG_NOCOOKIE)
    )
    req = struct.pack("BBBBI", family, IPPROTO_TCP, ext, 0, 0xFFFFFFFF) + sockid
    hdr = struct.pack(
        "IHHII",
        NLMSG_HDRLEN + len(req),
        SOCK_DIAG_BY_FAMILY,
        NLM_F_REQUEST | NLM_F_DUMP,
        1,
        0,
    )
    return hdr + req


def _recv_all(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        try:
            data = sock.recv(65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
        if len(data) < 16:
            break
        # Stop when this chunk contains NLMSG_DONE.
        off = 0
        done = False
        while off + NLMSG_HDRLEN <= len(data):
            nl_len, nl_type = struct.unpack_from("IH", data, off)
            if nl_len < NLMSG_HDRLEN:
                done = True
                break
            if nl_type in {NLMSG_DONE, NLMSG_ERROR}:
                done = True
                break
            off += _align(nl_len)
        if done:
            break
    return b"".join(chunks)


def dump_tcp_bytes() -> dict[int, TcpBytes]:
    out: dict[int, TcpBytes] = {}
    try:
        sock = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_SOCK_DIAG)
    except OSError:
        return out
    try:
        sock.bind((0, 0))
        sock.settimeout(1.0)
        for family in (socket.AF_INET, socket.AF_INET6):
            try:
                sock.send(_diag_request(family))
                out.update(parse_diag_dump(_recv_all(sock)))
            except OSError:
                continue
    finally:
        sock.close()
    return out
