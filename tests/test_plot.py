"""Optional PNG charts from host_net JSONL."""

from __future__ import annotations

import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eth_monitor.plot import chart_filename, pid_chart_filename, plot_run


def _net_line(ts: float, host: str, iface: str, rx: float, tx: float) -> str:
    return json.dumps(
        {
            "ts": ts,
            "host": host,
            "iface": iface,
            "eth_rx_bps": rx,
            "eth_tx_bps": tx,
        }
    ) + "\n"


class TestPlotRun(unittest.TestCase):
    def test_two_charts_per_iface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            series = run_dir / "series"
            series.mkdir()
            (series / "cn1_net.jsonl").write_text(
                _net_line(1.0, "cn1", "eth0", 0.0, 0.0)
                + _net_line(2.0, "cn1", "eth0", 10.0, 20.0),
                encoding="utf-8",
            )
            written: list[Path] = []

            def writer(path: Path, xs, ys, ylabel: str) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"PNG")
                written.append(path)

            out = plot_run(run_dir, writer=writer)
            names = sorted(p.name for p in out)
            self.assertEqual(
                names,
                [
                    chart_filename("cn1", "eth0", "eth_rx_bps"),
                    chart_filename("cn1", "eth0", "eth_tx_bps"),
                ],
            )
            self.assertTrue((run_dir / "charts" / names[0]).is_file())

    def test_skips_pid_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            series = run_dir / "series"
            series.mkdir()
            (series / "cn1_pid9.jsonl").write_text(
                json.dumps({"ts": 1, "host": "cn1", "pid": 9, "cpu_pct": 1}) + "\n",
                encoding="utf-8",
            )
            (series / "cn1_net.jsonl").write_text(
                _net_line(1.0, "cn1", "eth0", 1.0, 2.0),
                encoding="utf-8",
            )
            written: list[str] = []

            def writer(path: Path, xs, ys, ylabel: str) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"PNG")
                written.append(path.name)

            plot_run(run_dir, writer=writer)
            self.assertTrue(all("cpu" not in n for n in written))
            self.assertIn(chart_filename("cn1", "eth0", "eth_rx_bps"), written)

    def test_empty_series_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            series = run_dir / "series"
            series.mkdir()
            (series / "cn1_net.jsonl").write_text("", encoding="utf-8")
            buf = io.StringIO()
            out = plot_run(run_dir, writer=lambda *a, **k: None, warn_stream=buf)
            self.assertEqual(out, [])
            self.assertIn("skip empty", buf.getvalue())

    def test_missing_matplotlib_keeps_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            series = run_dir / "series"
            series.mkdir()
            path = series / "cn1_net.jsonl"
            path.write_text(_net_line(1.0, "cn1", "eth0", 1.0, 2.0), encoding="utf-8")
            buf = io.StringIO()
            import builtins

            real_import = builtins.__import__

            def fake_import(name, *args, **kwargs):
                if name == "matplotlib" or name.startswith("matplotlib."):
                    raise ImportError("no matplotlib")
                return real_import(name, *args, **kwargs)

            with mock.patch("builtins.__import__", fake_import):
                out = plot_run(run_dir, warn_stream=buf)
            self.assertEqual(out, [])
            self.assertTrue(path.is_file())
            self.assertIn("matplotlib", buf.getvalue())

    def test_pid_net_two_tcp_charts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            series = run_dir / "series"
            series.mkdir()
            (series / "cn1_pid42_net.jsonl").write_text(
                json.dumps(
                    {
                        "ts": 1.0,
                        "host": "cn1",
                        "pid": 42,
                        "comm": "app",
                        "tcp_rx_bps": 0.0,
                        "tcp_tx_bps": 0.0,
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "ts": 2.0,
                        "host": "cn1",
                        "pid": 42,
                        "comm": "app",
                        "tcp_rx_bps": 10.0,
                        "tcp_tx_bps": 20.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            written: list[str] = []

            def writer(path: Path, xs, ys, ylabel: str) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"PNG")
                written.append(path.name)

            out = plot_run(run_dir, writer=writer)
            names = sorted(p.name for p in out)
            self.assertEqual(
                names,
                [
                    pid_chart_filename("cn1", 42, "tcp_rx_bps"),
                    pid_chart_filename("cn1", 42, "tcp_tx_bps"),
                ],
            )
            self.assertTrue(all("eth_" not in n for n in written))

    def test_pid_net_does_not_emit_host_eth_charts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            series = run_dir / "series"
            series.mkdir()
            (series / "cn1_pid9_net.jsonl").write_text(
                json.dumps(
                    {
                        "ts": 1.0,
                        "host": "cn1",
                        "pid": 9,
                        "comm": "app",
                        "tcp_rx_bps": 1.0,
                        "tcp_tx_bps": 2.0,
                        "iface": "eth0",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            written: list[str] = []

            def writer(path: Path, xs, ys, ylabel: str) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"PNG")
                written.append(path.name)

            plot_run(run_dir, writer=writer)
            self.assertTrue(all("eth_" not in n for n in written))
            self.assertIn(pid_chart_filename("cn1", 9, "tcp_rx_bps"), written)


if __name__ == "__main__":
    unittest.main()
