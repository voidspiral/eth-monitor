"""Collect host ethernet samples to JSONL series files."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eth_monitor.net import NetCounters, parse_net_dev, select_ifaces

SAMPLE_KEYS = (
    "ts",
    "host",
    "iface",
    "eth_rx_bps",
    "eth_tx_bps",
)

NetDevReader = Callable[[], str]
SleepFn = Callable[[float], None]
NowFn = Callable[[], float]


def series_filename(host: str) -> str:
    return f"{host}_net.jsonl"


def series_path(output_dir: Path, host: str) -> Path:
    return output_dir / "series" / series_filename(host)


def append_sample(path: Path, sample: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sample, separators=(",", ":")) + "\n")


@dataclass
class _Prev:
    ts: float
    counters: dict[str, NetCounters]


def _bps(prev: int, cur: int, elapsed: float) -> float:
    if elapsed <= 0:
        return 0.0
    return max(cur - prev, 0) / elapsed


def _default_net_dev_reader(proc_net: Path) -> str:
    try:
        return proc_net.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def collect_loop(
    *,
    output_dir: Path,
    stop_file: Path,
    interval: float,
    host: str,
    proc_net: Path | None = None,
    sys_class_net: Path | None = None,
    net_dev_reader: NetDevReader | None = None,
    sleep_fn: SleepFn = time.sleep,
    now_fn: NowFn = time.time,
) -> None:
    proc_net = proc_net if proc_net is not None else Path("/proc/net/dev")
    sys_root = sys_class_net if sys_class_net is not None else Path("/sys/class/net")
    reader = net_dev_reader or (lambda: _default_net_dev_reader(proc_net))
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
        prev = _Prev(ts=ts, counters=counters)
        sleep_fn(interval)


def run_collect(
    *,
    output_dir: Path,
    stop_file: Path,
    interval: float = 1.0,
    host: str,
    proc_net: Path | None = None,
    sys_class_net: Path | None = None,
) -> int:
    collect_loop(
        output_dir=output_dir,
        stop_file=stop_file,
        interval=interval,
        host=host,
        proc_net=proc_net,
        sys_class_net=sys_class_net,
    )
    return 0
