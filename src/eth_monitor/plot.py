"""Plot host-ethernet and pid-tcp JSONL series to independently named PNG charts."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

METRICS = ("eth_rx_bps", "eth_tx_bps")
PID_METRICS = ("tcp_rx_bps", "tcp_tx_bps")
_PID_NET_RE = re.compile(r"^(?P<host>.+)_pid(?P<pid>\d+)_net\.jsonl$")

ChartWriter = Callable[[Path, list[float], list[float], str], None]


def chart_filename(host: str, iface: str, metric: str) -> str:
    return f"{host}_{iface}_{metric}.png"


def pid_chart_filename(host: str, pid: int, metric: str) -> str:
    return f"{host}_pid{pid}_{metric}.png"


def is_net_series(name: str) -> bool:
    return name.endswith("_net.jsonl") and "_pid" not in name


def is_pid_net_series(name: str) -> bool:
    return _PID_NET_RE.match(name) is not None


def load_samples(path: Path) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            samples.append(obj)
    return samples


def matplotlib_writer(path: Path, xs: list[float], ys: list[float], ylabel: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot(xs, ys)
    ax.set_xlabel("ts")
    ax.set_ylabel(ylabel)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def stub_writer(path: Path, xs: list[float], ys: list[float], ylabel: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PNG")


def plot_run(
    run_dir: Path,
    *,
    writer: ChartWriter | None = None,
    warn_stream: TextIO = sys.stderr,
) -> list[Path]:
    series_dir = run_dir / "series"
    charts_dir = run_dir / "charts"
    written: list[Path] = []
    if not series_dir.is_dir():
        return written

    if writer is None:
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            print("eth-monitor: matplotlib not available; skipping PNG charts", file=warn_stream)
            return written
        writer = matplotlib_writer

    for path in sorted(series_dir.glob("*.jsonl")):
        if is_pid_net_series(path.name):
            written.extend(_plot_pid_series(path, charts_dir, writer, warn_stream))
            continue
        if not is_net_series(path.name):
            continue
        samples = load_samples(path)
        if not samples:
            print(f"eth-monitor: skip empty series {path.name}", file=warn_stream)
            continue
        by_iface: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for sample in samples:
            iface = str(sample.get("iface") or "")
            if not iface:
                continue
            by_iface[iface].append(sample)
        if not by_iface:
            print(f"eth-monitor: skip empty series {path.name}", file=warn_stream)
            continue
        for iface, rows in by_iface.items():
            host = str(rows[0].get("host") or "")
            xs = [float(s.get("ts", 0.0)) for s in rows]
            for metric in METRICS:
                ys = [float(s.get(metric, 0.0)) for s in rows]
                out = charts_dir / chart_filename(host, iface, metric)
                writer(out, xs, ys, metric)
                written.append(out)
    return written


def _plot_pid_series(
    path: Path,
    charts_dir: Path,
    writer: ChartWriter,
    warn_stream: TextIO,
) -> list[Path]:
    parsed = _PID_NET_RE.match(path.name)
    samples = load_samples(path)
    if parsed is None or not samples:
        print(f"eth-monitor: skip empty series {path.name}", file=warn_stream)
        return []
    host = str(samples[0].get("host") or parsed.group("host"))
    pid = int(samples[0].get("pid") or parsed.group("pid"))
    xs = [float(s.get("ts", 0.0)) for s in samples]
    written: list[Path] = []
    for metric in PID_METRICS:
        ys = [float(s.get(metric, 0.0)) for s in samples]
        out = charts_dir / pid_chart_filename(host, pid, metric)
        writer(out, xs, ys, metric)
        written.append(out)
    return written
