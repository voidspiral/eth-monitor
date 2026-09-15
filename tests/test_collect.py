"""Collect loop stop-file and host_net JSONL schema."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from eth_monitor.collect import PID_SAMPLE_KEYS, SAMPLE_KEYS, collect_loop, pid_series_filename, series_filename
from eth_monitor.sockdiag import TcpBytes
from tests.test_net_parse import NET_DEV, _sysfs
from tests.test_proc import _write_stat


class TestCollectLoop(unittest.TestCase):
    def test_stop_file_exits_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            stop = out / "stop"
            stop.touch()
            reads = {"n": 0}

            def reader() -> str:
                reads["n"] += 1
                return NET_DEV

            collect_loop(
                output_dir=out,
                stop_file=stop,
                interval=0.01,
                host="h1",
                net_dev_reader=reader,
                sleep_fn=lambda _s: None,
            )
            self.assertEqual(reads["n"], 0)
            self.assertFalse((out / "series").exists())

    def test_writes_schema_and_zero_first_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sys_root = Path(tmp) / "sys"
            _sysfs(sys_root, "eth0", type_id="1", operstate="up")
            stop = out / "stop"
            ticks = {"n": 0}
            texts = [
                NET_DEV,
                NET_DEV.replace("1000", "3000").replace("2000", "5000"),
            ]

            def reader() -> str:
                i = min(ticks["n"], len(texts) - 1)
                ticks["n"] += 1
                if ticks["n"] >= 2:
                    stop.touch()
                return texts[i]

            times = iter([10.0, 12.0])

            collect_loop(
                output_dir=out,
                stop_file=stop,
                interval=0.01,
                host="cn1",
                net_dev_reader=reader,
                sys_class_net=sys_root,
                sleep_fn=lambda _s: None,
                now_fn=lambda: next(times, 12.0),
            )
            path = out / "series" / series_filename("cn1")
            self.assertTrue(path.is_file())
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreaterEqual(len(rows), 2)
            for row in rows:
                for key in SAMPLE_KEYS:
                    self.assertIn(key, row)
                self.assertEqual(row["host"], "cn1")
                self.assertEqual(row["iface"], "eth0")
            self.assertEqual(rows[0]["eth_rx_bps"], 0.0)
            self.assertEqual(rows[0]["eth_tx_bps"], 0.0)
            self.assertAlmostEqual(rows[1]["eth_rx_bps"], (3000 - 1000) / 2.0)
            self.assertAlmostEqual(rows[1]["eth_tx_bps"], (5000 - 2000) / 2.0)

    def test_one_file_per_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sys_root = Path(tmp) / "sys"
            _sysfs(sys_root, "eth0", type_id="1", operstate="up")
            stop = out / "stop"
            n = {"v": 0}

            def reader() -> str:
                n["v"] += 1
                if n["v"] >= 1:
                    stop.touch()
                return NET_DEV

            collect_loop(
                output_dir=out,
                stop_file=stop,
                interval=0.01,
                host="cn3",
                net_dev_reader=reader,
                sys_class_net=sys_root,
                sleep_fn=lambda _s: None,
                now_fn=lambda: 1.0,
            )
            files = list((out / "series").glob("*.jsonl"))
            self.assertEqual([p.name for p in files], ["cn3_net.jsonl"])

    def test_without_match_does_not_write_pid_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sys_root = Path(tmp) / "sys"
            proc = Path(tmp) / "proc"
            _sysfs(sys_root, "eth0", type_id="1", operstate="up")
            _fake_pid(proc, 9, "app", {9})
            stop = out / "stop"
            n = {"v": 0}

            def reader() -> str:
                n["v"] += 1
                if n["v"] >= 1:
                    stop.touch()
                return NET_DEV

            collect_loop(
                output_dir=out,
                stop_file=stop,
                interval=0.01,
                host="cn3",
                net_dev_reader=reader,
                sys_class_net=sys_root,
                proc_root=proc,
                diag_dump=lambda: {9: TcpBytes(1, 1, "bytes_sent", False)},
                sleep_fn=lambda _s: None,
                now_fn=lambda: 1.0,
            )
            files = sorted(p.name for p in (out / "series").glob("*.jsonl"))
            self.assertEqual(files, ["cn3_net.jsonl"])

    def test_match_writes_pid_schema_and_zero_first_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sys_root = Path(tmp) / "sys"
            proc = Path(tmp) / "proc"
            _sysfs(sys_root, "eth0", type_id="1", operstate="up")
            _fake_pid(proc, 42, "myapp", {7, 8})
            stop = out / "stop"
            ticks = {"n": 0}
            dumps = [
                {
                    7: TcpBytes(100, 200, "bytes_sent", False),
                    8: TcpBytes(10, 20, "bytes_sent", False),
                },
                {
                    7: TcpBytes(300, 400, "bytes_sent", False),
                    8: TcpBytes(10, 20, "bytes_sent", False),
                },
            ]

            def reader() -> str:
                ticks["n"] += 1
                if ticks["n"] >= 2:
                    stop.touch()
                return NET_DEV

            times = iter([10.0, 12.0])
            monos = iter([10.0, 12.0])
            n = {"i": 0}

            def diag_dump() -> dict[int, TcpBytes]:
                i = min(n["i"], len(dumps) - 1)
                n["i"] += 1
                return dumps[i]

            collect_loop(
                output_dir=out,
                stop_file=stop,
                interval=0.01,
                host="cn1",
                match="app",
                net_dev_reader=reader,
                sys_class_net=sys_root,
                proc_root=proc,
                diag_dump=diag_dump,
                sleep_fn=lambda _s: None,
                now_fn=lambda: next(times, 12.0),
                monotonic_fn=lambda: next(monos, 12.0),
            )
            path = out / "series" / pid_series_filename("cn1", 42)
            self.assertTrue(path.is_file())
            self.assertTrue((out / "series" / series_filename("cn1")).is_file())
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreaterEqual(len(rows), 2)
            for row in rows:
                for key in PID_SAMPLE_KEYS:
                    self.assertIn(key, row)
                self.assertEqual(row["host"], "cn1")
                self.assertEqual(row["pid"], 42)
                self.assertEqual(row["comm"], "myapp")
            self.assertEqual(rows[0]["tcp_rx_bps"], 0.0)
            self.assertEqual(rows[0]["tcp_tx_bps"], 0.0)
            self.assertEqual(rows[0]["process_starttime_ticks"], 1000)
            self.assertAlmostEqual(rows[1]["tcp_rx_bps"], (310 - 110) / 2.0)
            self.assertAlmostEqual(rows[1]["tcp_tx_bps"], (420 - 220) / 2.0)
            self.assertFalse((out / "tcp_info_partial").exists())

    def test_partial_tcp_info_writes_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sys_root = Path(tmp) / "sys"
            proc = Path(tmp) / "proc"
            _sysfs(sys_root, "eth0", type_id="1", operstate="up")
            _fake_pid(proc, 5, "app", {1})
            stop = out / "stop"
            n = {"v": 0}

            def reader() -> str:
                n["v"] += 1
                if n["v"] >= 1:
                    stop.touch()
                return NET_DEV

            collect_loop(
                output_dir=out,
                stop_file=stop,
                interval=0.01,
                host="h",
                match="app",
                net_dev_reader=reader,
                sys_class_net=sys_root,
                proc_root=proc,
                diag_dump=lambda: {1: TcpBytes(4, 5, "bytes_acked", True)},
                sleep_fn=lambda _s: None,
                now_fn=lambda: 1.0,
            )
            self.assertTrue((out / "tcp_info_partial").is_file())

    def test_unreadable_diag_is_fail_soft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            sys_root = Path(tmp) / "sys"
            proc = Path(tmp) / "proc"
            _sysfs(sys_root, "eth0", type_id="1", operstate="up")
            _fake_pid(proc, 5, "app", {1})
            stop = out / "stop"
            n = {"v": 0}

            def reader() -> str:
                n["v"] += 1
                if n["v"] >= 1:
                    stop.touch()
                return NET_DEV

            def boom() -> dict[int, TcpBytes]:
                raise OSError("no diag")

            collect_loop(
                output_dir=out,
                stop_file=stop,
                interval=0.01,
                host="h",
                match="app",
                net_dev_reader=reader,
                sys_class_net=sys_root,
                proc_root=proc,
                diag_dump=boom,
                sleep_fn=lambda _s: None,
                now_fn=lambda: 1.0,
            )
            self.assertTrue((out / "series" / series_filename("h")).is_file())

    def test_closed_socket_does_not_cancel_remaining(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out, sys_root, proc, stop = _pid_setup(tmp)
            _fake_pid(proc, 42, "app", {7, 8}, starttime=5)
            dumps = [
                {
                    7: TcpBytes(100, 200, "bytes_sent", False),
                    8: TcpBytes(10, 20, "bytes_sent", False),
                },
                {
                    8: TcpBytes(10, 40, "bytes_sent", False),
                },
            ]
            rows = _collect_pid_rows(
                out, sys_root, proc, stop, dumps, pid=42, host="cn1", monos=(1.0, 3.0)
            )
            self.assertEqual(rows[0]["tcp_tx_bps"], 0.0)
            self.assertAlmostEqual(rows[1]["tcp_tx_bps"], 20.0 / 2.0)
            self.assertEqual(rows[1]["tcp_rx_bps"], 0.0)

    def test_new_socket_on_known_process_uses_current_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out, sys_root, proc, stop = _pid_setup(tmp)
            _fake_pid(proc, 42, "app", {7}, starttime=5)
            dumps = [
                {7: TcpBytes(10, 20, "bytes_sent", False)},
                {
                    7: TcpBytes(10, 20, "bytes_sent", False),
                    9: TcpBytes(0, 50, "bytes_sent", False),
                },
            ]
            # second tick also has inode 9 in /proc
            def reader_factory():
                ticks = {"n": 0}

                def reader() -> str:
                    ticks["n"] += 1
                    if ticks["n"] == 2:
                        _fake_pid(proc, 42, "app", {7, 9}, starttime=5)
                    if ticks["n"] >= 2:
                        stop.touch()
                    return NET_DEV

                return reader

            n = {"i": 0}

            def diag_dump() -> dict[int, TcpBytes]:
                i = min(n["i"], len(dumps) - 1)
                n["i"] += 1
                return dumps[i]

            monos = iter([1.0, 3.0])
            collect_loop(
                output_dir=out,
                stop_file=stop,
                interval=0.01,
                host="cn1",
                match="app",
                net_dev_reader=reader_factory(),
                sys_class_net=sys_root,
                proc_root=proc,
                diag_dump=diag_dump,
                sleep_fn=lambda _s: None,
                now_fn=lambda: 1.0,
                monotonic_fn=lambda: next(monos, 3.0),
            )
            rows = _load_pid_rows(out, "cn1", 42)
            self.assertAlmostEqual(rows[1]["tcp_tx_bps"], 50.0 / 2.0)

    def test_pid_reuse_first_sample_is_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out, sys_root, proc, stop = _pid_setup(tmp)
            _fake_pid(proc, 42, "app", {7}, starttime=10)
            dumps = [
                {7: TcpBytes(100, 200, "bytes_sent", False)},
                {7: TcpBytes(500, 900, "bytes_sent", False)},
            ]
            ticks = {"n": 0}

            def reader() -> str:
                ticks["n"] += 1
                if ticks["n"] == 2:
                    _fake_pid(proc, 42, "app", {7}, starttime=99)
                if ticks["n"] >= 2:
                    stop.touch()
                return NET_DEV

            n = {"i": 0}

            def diag_dump() -> dict[int, TcpBytes]:
                i = min(n["i"], len(dumps) - 1)
                n["i"] += 1
                return dumps[i]

            monos = iter([1.0, 3.0])
            collect_loop(
                output_dir=out,
                stop_file=stop,
                interval=0.01,
                host="cn1",
                match="app",
                net_dev_reader=reader,
                sys_class_net=sys_root,
                proc_root=proc,
                diag_dump=diag_dump,
                sleep_fn=lambda _s: None,
                now_fn=lambda: 1.0,
                monotonic_fn=lambda: next(monos, 3.0),
            )
            rows = _load_pid_rows(out, "cn1", 42)
            self.assertEqual(rows[0]["process_starttime_ticks"], 10)
            self.assertEqual(rows[1]["process_starttime_ticks"], 99)
            self.assertEqual(rows[1]["tcp_rx_bps"], 0.0)
            self.assertEqual(rows[1]["tcp_tx_bps"], 0.0)

    def test_shared_socket_counts_only_lowest_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out, sys_root, proc, stop = _pid_setup(tmp)
            _fake_pid(proc, 10, "app", {5}, starttime=1)
            _fake_pid(proc, 20, "app", {5, 9}, starttime=2)
            dumps = [
                {
                    5: TcpBytes(0, 100, "bytes_sent", False),
                    9: TcpBytes(0, 7, "bytes_sent", False),
                },
                {
                    5: TcpBytes(0, 300, "bytes_sent", False),
                    9: TcpBytes(0, 7, "bytes_sent", False),
                },
            ]
            ticks = {"n": 0}

            def reader() -> str:
                ticks["n"] += 1
                if ticks["n"] >= 2:
                    stop.touch()
                return NET_DEV

            n = {"i": 0}

            def diag_dump() -> dict[int, TcpBytes]:
                i = min(n["i"], len(dumps) - 1)
                n["i"] += 1
                return dumps[i]

            monos = iter([1.0, 3.0])
            collect_loop(
                output_dir=out,
                stop_file=stop,
                interval=0.01,
                host="cn1",
                match="app",
                net_dev_reader=reader,
                sys_class_net=sys_root,
                proc_root=proc,
                diag_dump=diag_dump,
                sleep_fn=lambda _s: None,
                now_fn=lambda: 1.0,
                monotonic_fn=lambda: next(monos, 3.0),
            )
            low = _load_pid_rows(out, "cn1", 10)
            high = _load_pid_rows(out, "cn1", 20)
            self.assertAlmostEqual(low[1]["tcp_tx_bps"], 200.0 / 2.0)
            self.assertEqual(high[1]["tcp_tx_bps"], 0.0)

    def test_pid_elapsed_uses_monotonic_not_wall_clock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out, sys_root, proc, stop = _pid_setup(tmp)
            _fake_pid(proc, 42, "app", {7}, starttime=5)
            dumps = [
                {7: TcpBytes(0, 0, "bytes_sent", False)},
                {7: TcpBytes(0, 40, "bytes_sent", False)},
            ]
            rows = _collect_pid_rows(
                out,
                sys_root,
                proc,
                stop,
                dumps,
                pid=42,
                host="h",
                times=(100.0, 50.0),
                monos=(1.0, 3.0),
            )
            self.assertAlmostEqual(rows[1]["tcp_tx_bps"], 40.0 / 2.0)


def _pid_setup(tmp: str) -> tuple[Path, Path, Path, Path]:
    out = Path(tmp)
    sys_root = out / "sys"
    proc = out / "proc"
    _sysfs(sys_root, "eth0", type_id="1", operstate="up")
    stop = out / "stop"
    return out, sys_root, proc, stop


def _collect_pid_rows(
    out: Path,
    sys_root: Path,
    proc: Path,
    stop: Path,
    dumps: list[dict[int, TcpBytes]],
    *,
    pid: int,
    host: str,
    times: tuple[float, float] = (10.0, 12.0),
    monos: tuple[float, float] = (10.0, 12.0),
) -> list[dict]:
    ticks = {"n": 0}

    def reader() -> str:
        ticks["n"] += 1
        if ticks["n"] >= 2:
            stop.touch()
        return NET_DEV

    n = {"i": 0}

    def diag_dump() -> dict[int, TcpBytes]:
        i = min(n["i"], len(dumps) - 1)
        n["i"] += 1
        return dumps[i]

    time_iter = iter(times)
    mono_iter = iter(monos)
    collect_loop(
        output_dir=out,
        stop_file=stop,
        interval=0.01,
        host=host,
        match="app",
        net_dev_reader=reader,
        sys_class_net=sys_root,
        proc_root=proc,
        diag_dump=diag_dump,
        sleep_fn=lambda _s: None,
        now_fn=lambda: next(time_iter, times[-1]),
        monotonic_fn=lambda: next(mono_iter, monos[-1]),
    )
    return _load_pid_rows(out, host, pid)


def _load_pid_rows(out: Path, host: str, pid: int) -> list[dict]:
    path = out / "series" / pid_series_filename(host, pid)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fake_pid(proc: Path, pid: int, comm: str, inodes: set[int], starttime: int = 1000) -> None:
    fd = proc / str(pid) / "fd"
    if fd.exists():
        for child in fd.iterdir():
            child.unlink()
    else:
        fd.mkdir(parents=True)
    (proc / str(pid) / "comm").write_text(comm + "\n", encoding="utf-8")
    _write_stat(proc, pid, comm, starttime)
    for i, inode in enumerate(sorted(inodes)):
        os.symlink(f"socket:[{inode}]", fd / str(i + 3))


if __name__ == "__main__":
    unittest.main()
