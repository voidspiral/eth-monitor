"""Collect host ethernet samples to JSONL series files."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eth_monitor.net import NetCounters, parse_net_dev, select_ifaces
from eth_monitor.proc import inode_owners, list_matched_pids
from eth_monitor.sockdiag import TcpBytes, dump_tcp_bytes

SAMPLE_KEYS = (
    "ts",
    "host",
    "iface",
    "eth_rx_bps",
    "eth_tx_bps",
)
PID_SAMPLE_KEYS = (
    "ts",
    "host",
    "pid",
    "comm",
    "process_starttime_ticks",
    "tcp_rx_bps",
    "tcp_tx_bps",
)

NetDevReader = Callable[[], str]
DiagDumpFn = Callable[[], dict[int, TcpBytes]]
SleepFn = Callable[[float], None]
NowFn = Callable[[], float]
SocketKey = tuple[int, int, int, tuple[int, int]]


def series_filename(host: str) -> str:
    return f"{host}_net.jsonl"


def pid_series_filename(host: str, pid: int) -> str:
    return f"{host}_pid{pid}_net.jsonl"


def series_path(output_dir: Path, host: str) -> Path:
    return output_dir / "series" / series_filename(host)


def pid_series_path(output_dir: Path, host: str, pid: int) -> Path:
    return output_dir / "series" / pid_series_filename(host, pid)


def append_sample(path: Path, sample: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sample, separators=(",", ":")) + "\n")


@dataclass
class _Prev:
    ts: float
    counters: dict[str, NetCounters]
    pid_mono: float | None
    seen_procs: set[tuple[int, int]]
    sockets: dict[SocketKey, tuple[int, int]]


def _bps(prev: int, cur: int, elapsed: float) -> float:
    if elapsed <= 0:
        return 0.0
    return max(cur - prev, 0) / elapsed


def _default_net_dev_reader(proc_net: Path) -> str:
    try:
        return proc_net.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _write_partial_marker(output_dir: Path) -> None:
    marker = output_dir / "tcp_info_partial"
    if marker.exists():
        return
    try:
        marker.write_text("true\n", encoding="utf-8")
    except OSError:
        return


def collect_loop(
    *,
    output_dir: Path,
    stop_file: Path,
    interval: float,
    host: str,
    match: str | None = None,
    proc_net: Path | None = None,
    sys_class_net: Path | None = None,
    proc_root: Path | None = None,
    net_dev_reader: NetDevReader | None = None,
    diag_dump: DiagDumpFn | None = None,
    sleep_fn: SleepFn = time.sleep,
    now_fn: NowFn = time.time,
    monotonic_fn: NowFn = time.monotonic,
) -> None:
    proc_net = proc_net if proc_net is not None else Path("/proc/net/dev")
    sys_root = sys_class_net if sys_class_net is not None else Path("/sys/class/net")
    proc = proc_root if proc_root is not None else Path("/proc")
    reader = net_dev_reader or (lambda: _default_net_dev_reader(proc_net))
    dump_fn = diag_dump if diag_dump is not None else dump_tcp_bytes
    prev: _Prev | None = None
    dest = series_path(output_dir, host)

    while True:
        if stop_file.exists():
            return
        text = reader()
        counters = parse_net_dev(text)
        ifaces = select_ifaces(counters, sys_class_net=sys_root)
        ts = now_fn()
        elapsed = 0.0 if prev is None else max(ts - prev.ts, 0.0)
        for iface in ifaces:
            cur = counters[iface]
            old = None if prev is None else prev.counters.get(iface)
            sample = {
                "ts": ts,
                "host": host,
                "iface": iface,
                "eth_rx_bps": 0.0 if old is None else _bps(old.rx_bytes, cur.rx_bytes, elapsed),
                "eth_tx_bps": 0.0 if old is None else _bps(old.tx_bytes, cur.tx_bytes, elapsed),
                "eth_rx_pps": 0.0 if old is None else _bps(old.rx_packets, cur.rx_packets, elapsed),
                "eth_tx_pps": 0.0 if old is None else _bps(old.tx_packets, cur.tx_packets, elapsed),
            }
            for key in SAMPLE_KEYS:
                if key not in sample:
                    raise ValueError(f"sample missing {key}")
            append_sample(dest, sample)
        seen_procs: set[tuple[int, int]] = set() if prev is None else set(prev.seen_procs)
        sockets: dict[SocketKey, tuple[int, int]] = {} if prev is None else dict(prev.sockets)
        pid_mono = prev.pid_mono if prev is not None else None
        if match:
            try:
                dumped = dump_fn()
            except OSError:
                dumped = {}
            matched = list_matched_pids(proc, match)
            owners = inode_owners(matched)
            pid_mono = monotonic_fn()
            tcp_elapsed = 0.0 if prev is None or prev.pid_mono is None else max(pid_mono - prev.pid_mono, 0.0)
            seen_procs = set()
            sockets = {}
            for item in matched:
                instance = (item.pid, item.starttime_ticks)
                seen_procs.add(instance)
                known = prev is not None and instance in prev.seen_procs
                drx = 0
                dtx = 0
                for inode in item.inodes:
                    if owners.get(inode) != item.pid:
                        continue
                    counters_tcp = dumped.get(inode)
                    if counters_tcp is None:
                        continue
                    if counters_tcp.partial:
                        _write_partial_marker(output_dir)
                    cookie = counters_tcp.cookie
                    key = (item.pid, item.starttime_ticks, inode, cookie)
                    sockets[key] = (counters_tcp.rx, counters_tcp.tx)
                    if not known:
                        continue
                    old_sock = prev.sockets.get(key) if prev is not None else None
                    if old_sock is None:
                        drx += counters_tcp.rx
                        dtx += counters_tcp.tx
                    else:
                        drx += max(counters_tcp.rx - old_sock[0], 0)
                        dtx += max(counters_tcp.tx - old_sock[1], 0)
                pid_sample = {
                    "ts": ts,
                    "host": host,
                    "pid": item.pid,
                    "comm": item.comm,
                    "process_starttime_ticks": item.starttime_ticks,
                    "tcp_rx_bps": 0.0 if (not known or tcp_elapsed <= 0) else drx / tcp_elapsed,
                    "tcp_tx_bps": 0.0 if (not known or tcp_elapsed <= 0) else dtx / tcp_elapsed,
                }
                for key_name in PID_SAMPLE_KEYS:
                    if key_name not in pid_sample:
                        raise ValueError(f"sample missing {key_name}")
                append_sample(pid_series_path(output_dir, host, item.pid), pid_sample)
        prev = _Prev(
            ts=ts,
            counters=counters,
            pid_mono=pid_mono,
            seen_procs=seen_procs,
            sockets=sockets,
        )
        sleep_fn(interval)


def run_collect(
    *,
    output_dir: Path,
    stop_file: Path,
    interval: float = 1.0,
    host: str,
    match: str | None = None,
    proc_net: Path | None = None,
    sys_class_net: Path | None = None,
    proc_root: Path | None = None,
) -> int:
    collect_loop(
        output_dir=output_dir,
        stop_file=stop_file,
        interval=interval,
        host=host,
        match=match,
        proc_net=proc_net,
        sys_class_net=sys_class_net,
        proc_root=proc_root,
    )
    return 0
