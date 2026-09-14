"""CLI wrap / remote-cmd / probe tests."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import base64
import io
import json
import socket
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from eth_monitor.cli import main
from eth_monitor.remote import remote_cmd


class TestCli(unittest.TestCase):
    def test_probe_ok(self) -> None:
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = main(["probe"])
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue().strip(), "ok")

    def test_wrap_without_hosts_exits_nonzero(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main(["wrap", "--output-dir", "/tmp", "--", "true"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_wrap_empty_hosts_exits_nonzero(self) -> None:
        code = main(["wrap", "--hosts", ",", "--output-dir", "/tmp", "--", "true"])
        self.assertEqual(code, 2)

    def test_remote_cmd_stdout_is_decodable_python_payload(self) -> None:
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            code = main(["remote-cmd"])
        self.assertEqual(code, 0)
        line = buf.getvalue().strip()
        self.assertIn("base64 -d", line)
        inner = line.split()[1]
        boot = base64.b64decode(inner).decode("utf-8")
        self.assertIn("from eth_monitor.cli import main", boot)
        marker = "b64decode('"
        start = boot.index(marker) + len(marker)
        end = boot.index("')", start)
        raw = base64.b64decode(boot[start:end])
        names = zipfile.ZipFile(io.BytesIO(raw)).namelist()
        self.assertIn("eth_monitor/cli.py", names)
        self.assertIn("eth_monitor/collect.py", names)
        self.assertIn("eth_monitor/proc.py", names)
        self.assertIn("eth_monitor/sockdiag.py", names)
        self.assertIn("base64 -d", remote_cmd())

    def test_local_wrap_preserves_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            host = socket.gethostname().split(".")[0]
            code = main(
                [
                    "wrap",
                    "--hosts",
                    host,
                    "--output-dir",
                    tmp,
                    "--interval",
                    "0.05",
                    "--join-timeout",
                    "2",
                    "--no-plot",
                    "--",
                    sys.executable,
                    "-c",
                    "import time,sys; time.sleep(0.2); sys.exit(7)",
                ]
            )
            self.assertEqual(code, 7)
            runs = [p for p in Path(tmp).iterdir() if p.is_dir()]
            self.assertEqual(len(runs), 1)
            meta = json.loads((runs[0] / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["application_exit_code"], 7)

    def test_wrap_accepts_explicit_run_id_and_no_plot(self) -> None:
        with mock.patch("eth_monitor.cli.wrap", return_value=0) as wrapped:
            code = main(
                [
                    "wrap",
                    "--hosts",
                    "cn1",
                    "--output-dir",
                    "/tmp/out",
                    "--run-id",
                    "fixed-run",
                    "--no-plot",
                    "--",
                    "true",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(wrapped.call_args.kwargs["run_id"], "fixed-run")
        self.assertFalse(wrapped.call_args.kwargs["plot"])

    def test_wrap_forwards_match(self) -> None:
        with mock.patch("eth_monitor.cli.wrap", return_value=0) as wrapped:
            code = main(
                [
                    "wrap",
                    "--hosts",
                    "cn1",
                    "--output-dir",
                    "/tmp/out",
                    "--match",
                    "app",
                    "--no-plot",
                    "--",
                    "true",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(wrapped.call_args.kwargs["match"], "app")

    def test_collect_forwards_match(self) -> None:
        with mock.patch("eth_monitor.cli.run_collect", return_value=0) as collect:
            code = main(
                [
                    "collect",
                    "--output-dir",
                    "/tmp/out",
                    "--stop-file",
                    "/tmp/stop",
                    "--host",
                    "cn1",
                    "--match",
                    "app",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(collect.call_args.kwargs["match"], "app")


if __name__ == "__main__":
    unittest.main()
