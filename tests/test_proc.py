"""Fake /proc comm match and socket inode tests."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import os
import tempfile
import unittest
from pathlib import Path

from eth_monitor.proc import list_matched_pids, socket_inodes


def _pid_dir(proc: Path, pid: int) -> Path:
    d = proc / str(pid)
    (d / "fd").mkdir(parents=True)
    return d


def _write_comm(proc: Path, pid: int, comm: str) -> None:
    d = _pid_dir(proc, pid) if not (proc / str(pid)).is_dir() else proc / str(pid)
    (d / "fd").mkdir(exist_ok=True)
    (d / "comm").write_text(comm + "\n", encoding="utf-8")


def _link_fd(proc: Path, pid: int, fd: int, target: str) -> None:
    os.symlink(target, proc / str(pid) / "fd" / str(fd))


class TestProcMatch(unittest.TestCase):
    def test_match_is_case_sensitive_substring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            _write_comm(proc, 10, "myapp")
            _write_comm(proc, 11, "MyApp")
            _write_comm(proc, 12, "helper-myapp-worker")
            _link_fd(proc, 10, 3, "socket:[100]")
            _link_fd(proc, 12, 3, "socket:[200]")
            found = {m.pid: m for m in list_matched_pids(proc, "myapp")}
            self.assertEqual(set(found), {10, 12})
            self.assertEqual(found[10].comm, "myapp")
            self.assertEqual(found[12].comm, "helper-myapp-worker")

    def test_socket_inodes_dedupe_and_ignore_nonsockets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            _write_comm(proc, 7, "app")
            _link_fd(proc, 7, 0, "/dev/null")
            _link_fd(proc, 7, 3, "socket:[42]")
            _link_fd(proc, 7, 4, "socket:[42]")
            _link_fd(proc, 7, 5, "socket:[99]")
            self.assertEqual(socket_inodes(proc, 7), {42, 99})

    def test_unreadable_pid_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            _write_comm(proc, 1, "app")
            _link_fd(proc, 1, 3, "socket:[1]")
            broken = proc / "2"
            broken.mkdir()
            (broken / "fd").mkdir()
            found = list_matched_pids(proc, "app")
            self.assertEqual([m.pid for m in found], [1])

    def test_empty_match_returns_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            _write_comm(proc, 3, "app")
            self.assertEqual(list_matched_pids(proc, ""), [])
            self.assertEqual(list_matched_pids(proc, None), [])


if __name__ == "__main__":
    unittest.main()
