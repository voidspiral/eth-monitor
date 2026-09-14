"""Scan /proc for matching PIDs and TCP socket inodes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_SOCKET_PREFIX = "socket:["


@dataclass(frozen=True)
class MatchedPid:
    pid: int
    comm: str
    inodes: frozenset[int]


def _read_comm(proc_root: Path, pid: int) -> str | None:
    path = proc_root / str(pid) / "comm"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return text.strip()


def socket_inodes(proc_root: Path, pid: int) -> set[int]:
    fd_dir = proc_root / str(pid) / "fd"
    out: set[int] = set()
    try:
        names = os.listdir(fd_dir)
    except OSError:
        return out
    for name in names:
        try:
            target = os.readlink(fd_dir / name)
        except OSError:
            continue
        if not target.startswith(_SOCKET_PREFIX) or not target.endswith("]"):
            continue
        inner = target[len(_SOCKET_PREFIX) : -1]
        try:
            out.add(int(inner))
        except ValueError:
            continue
    return out


def list_matched_pids(proc_root: Path, match: str | None) -> list[MatchedPid]:
    if not match:
        return []
    found: list[MatchedPid] = []
    try:
        entries = os.listdir(proc_root)
    except OSError:
        return []
    for name in entries:
        if not name.isdigit():
            continue
        pid = int(name)
        comm = _read_comm(proc_root, pid)
        if comm is None or match not in comm:
            continue
        inodes = frozenset(socket_inodes(proc_root, pid))
        found.append(MatchedPid(pid=pid, comm=comm, inodes=inodes))
    found.sort(key=lambda m: m.pid)
    return found
