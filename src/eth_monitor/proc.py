"""Scan /proc for matching PIDs and TCP socket inodes."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_SOCKET_PREFIX = "socket:["
_STARTTIME_INDEX = 19  # 0-based field after comm in /proc/<pid>/stat


@dataclass(frozen=True)
class MatchedPid:
    pid: int
    comm: str
    starttime_ticks: int
    inodes: frozenset[int]


def _read_comm(proc_root: Path, pid: int) -> str | None:
    path = proc_root / str(pid) / "comm"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return text.strip()


def read_starttime_ticks(proc_root: Path, pid: int) -> int | None:
    path = proc_root / str(pid) / "stat"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    rpar = text.rfind(")")
    if rpar < 0:
        return None
    rest = text[rpar + 1 :].split()
    if len(rest) <= _STARTTIME_INDEX:
        return None
    try:
        return int(rest[_STARTTIME_INDEX])
    except ValueError:
        return None


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
        starttime = read_starttime_ticks(proc_root, pid)
        if starttime is None:
            continue
        inodes = frozenset(socket_inodes(proc_root, pid))
        found.append(MatchedPid(pid=pid, comm=comm, starttime_ticks=starttime, inodes=inodes))
    found.sort(key=lambda m: m.pid)
    return found


def inode_owners(matched: Sequence[MatchedPid]) -> dict[int, int]:
    owners: dict[int, int] = {}
    for item in matched:
        for inode in item.inodes:
            prev = owners.get(inode)
            if prev is None or item.pid < prev:
                owners[inode] = item.pid
    return owners
