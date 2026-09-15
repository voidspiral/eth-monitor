"""Fake /proc comm match and socket inode tests."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import os
import tempfile
import unittest
from pathlib import Path

from eth_monitor.proc import inode_owners, list_matched_pids, socket_inodes


def _pid_dir(proc: Path, pid: int) -> Path:
    d = proc / str(pid)
    (d / "fd").mkdir(parents=True)
    return d


def _write_stat(proc: Path, pid: int, comm: str, starttime: int, state: str = "R") -> None:
    d = proc / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    tokens = [state] + ["0"] * 19
    tokens[19] = str(starttime)
    (d / "stat").write_text(f"{pid} ({comm}) " + " ".join(tokens) + "\n", encoding="utf-8")


def _write_comm(proc: Path, pid: int, comm: str, starttime: int = 1000) -> None:
    d = _pid_dir(proc, pid) if not (proc / str(pid)).is_dir() else proc / str(pid)
    (d / "fd").mkdir(exist_ok=True)
    (d / "comm").write_text(comm + "\n", encoding="utf-8")
    _write_stat(proc, pid, comm, starttime)


def _write_cmdline(proc: Path, pid: int, *argv: str) -> None:
    (proc / str(pid) / "cmdline").write_bytes(
        b"\0".join(arg.encode("utf-8") for arg in argv) + b"\0"
    )


def _link_fd(proc: Path, pid: int, fd: int, target: str) -> None:
    os.symlink(target, proc / str(pid) / "fd" / str(fd))


class TestProcMatch(unittest.TestCase):
    def test_long_binary_name_matches_argv0_when_comm_is_truncated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            _write_comm(proc, 13, "mpi_fault_segfa")
            _write_cmdline(
                proc,
                13,
                "/shared/agent-sidecar/examples/mpi_fault_segfault",
                "10",
                "0",
            )
            found = list_matched_pids(proc, "mpi_fault_segfault")
            self.assertEqual([item.pid for item in found], [13])

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

    def test_starttime_parses_comm_with_spaces_and_parentheses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            comm = "my app (worker)"
            _write_comm(proc, 4, comm, starttime=4242)
            found = list_matched_pids(proc, "my app")
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].pid, 4)
            self.assertEqual(found[0].starttime_ticks, 4242)

    def test_missing_stat_skips_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            _write_comm(proc, 8, "app", starttime=1)
            (proc / "8" / "stat").unlink()
            self.assertEqual(list_matched_pids(proc, "app"), [])

    def test_shared_inode_owner_is_lowest_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = Path(tmp)
            _write_comm(proc, 20, "app", starttime=2)
            _write_comm(proc, 10, "app", starttime=1)
            _link_fd(proc, 10, 3, "socket:[5]")
            _link_fd(proc, 20, 3, "socket:[5]")
            _link_fd(proc, 20, 4, "socket:[9]")
            matched = list_matched_pids(proc, "app")
            owners = inode_owners(matched)
            self.assertEqual(owners[5], 10)
            self.assertEqual(owners[9], 20)


if __name__ == "__main__":
    unittest.main()
