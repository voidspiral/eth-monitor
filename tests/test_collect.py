"""Collect loop stop-file and host_net JSONL schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from eth_monitor.collect import SAMPLE_KEYS, collect_loop, series_filename
from tests.test_net_parse import NET_DEV, _sysfs


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


if __name__ == "__main__":
    unittest.main()
