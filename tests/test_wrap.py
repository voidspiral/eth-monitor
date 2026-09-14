"""Local vs remote host routing for wrap."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import base64
import io
import json
import subprocess
import tarfile
import tempfile
import time
import unittest
from pathlib import Path

from eth_monitor.wrap import _remote_finalize_command, is_local_host, wrap


class _DoneHandle:
    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        return None


class HangHandle:
    def __init__(self) -> None:
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        if timeout is None:
            time.sleep(30)
            return 0
        time.sleep(min(timeout, 0.05))
        raise subprocess.TimeoutExpired(cmd="collect", timeout=timeout)

    def kill(self) -> None:
        self.killed = True


class TestWrapHosts(unittest.TestCase):
    @staticmethod
    def _series_archive(name: str = "cn2_net.jsonl") -> str:
        payload = b'{"host":"cn2","iface":"eth0","eth_rx_bps":0}\n'
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            info = tarfile.TarInfo(f"series/{name}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        return base64.b64encode(stream.getvalue()).decode()

    def test_localhost_aliases_are_local(self) -> None:
        self.assertTrue(is_local_host("localhost", local="cn1"))
        self.assertTrue(is_local_host("cn1", local="cn1"))
        self.assertTrue(is_local_host("cn1.cluster", local="cn1"))
        self.assertFalse(is_local_host("cn2", local="cn1"))

    def test_local_host_does_not_ssh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ssh_calls: list[tuple] = []
            local_calls: list[str] = []

            def spawn_local(**kwargs):
                local_calls.append(kwargs["host"])
                return _DoneHandle()

            def ssh_run(host, command, **kwargs):
                ssh_calls.append((host, command))
                return subprocess.CompletedProcess(["ssh"], 0, stdout="", stderr="")

            code = wrap(
                ["true"],
                hosts=["cn1"],
                output_dir=Path(tmp),
                local_host="cn1",
                run_command=lambda _c: 0,
                spawn_local=spawn_local,
                ssh_run=ssh_run,
                plot=False,
                join_timeout=0.2,
            )
            self.assertEqual(code, 0)
            self.assertEqual(local_calls, ["cn1"])
            self.assertEqual(ssh_calls, [])

    def test_remote_host_uses_ssh_and_fetches_net_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            commands: list[str] = []

            def spawn_local(**kwargs):
                raise AssertionError("should not spawn local")

            def ssh_run(host, command, **kwargs):
                commands.append(command)
                stdout = self._series_archive() if "base64" in command else "OK\n"
                return subprocess.CompletedProcess(["ssh"], 0, stdout=stdout, stderr="")

            code = wrap(
                ["true"],
                hosts=["cn2"],
                output_dir=Path(tmp),
                local_host="cn1",
                run_command=lambda _c: 7,
                spawn_local=spawn_local,
                ssh_run=ssh_run,
                plot=False,
                join_timeout=0.5,
                run_id="run-test",
            )
            self.assertEqual(code, 7)
            start = next(c for c in commands if "setsid bash -c" in c)
            self.assertIn("eth-monitor", start)
            self.assertNotIn("--match", start)
            series = Path(tmp) / "run-test/series/cn2_net.jsonl"
            self.assertTrue(series.is_file())

    def test_join_is_bounded_and_stop_file_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handle = HangHandle()
            started = time.monotonic()
            code = wrap(
                ["true"],
                hosts=["cn1"],
                output_dir=Path(tmp),
                local_host="cn1",
                run_command=lambda _c: 0,
                spawn_local=lambda **_k: handle,
                plot=False,
                join_timeout=0.3,
                run_id="stop-test",
            )
            elapsed = time.monotonic() - started
            self.assertEqual(code, 0)
            self.assertLess(elapsed, 2.0)
            self.assertTrue(handle.killed)
            self.assertTrue((Path(tmp) / "stop-test" / "stop").exists())

    def test_finalize_kills_instead_of_pid_wait_loop(self) -> None:
        command = _remote_finalize_command("/tmp/eth-monitor/run/cn2")
        self.assertIn("touch ", command)
        self.assertIn("kill ", command)
        self.assertIn("tar -C", command)
        self.assertNotIn("while kill -0", command)

    def test_empty_hosts_returns_2(self) -> None:
        code = wrap(["true"], hosts=[], output_dir=Path("/tmp"), plot=False)
        self.assertEqual(code, 2)

    def test_remote_timeout_is_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:

            def ssh_run(host, command, **kwargs):
                if "setsid bash -c" in command:
                    return subprocess.CompletedProcess(["ssh"], 0, stdout="OK\n", stderr="")
                raise subprocess.TimeoutExpired(["ssh"], kwargs.get("timeout"))

            code = wrap(
                ["true"],
                hosts=["cn2"],
                output_dir=Path(tmp),
                local_host="cn1",
                run_command=lambda _c: 0,
                spawn_local=lambda **_k: _DoneHandle(),
                ssh_run=ssh_run,
                plot=False,
                join_timeout=0.01,
                run_id="run-timeout",
            )
            self.assertEqual(code, 0)
            meta = json.loads((Path(tmp) / "run-timeout/meta.json").read_text())
            self.assertEqual(meta["application_exit_code"], 0)
            self.assertEqual(meta["collection_status"], "partial")
            self.assertIn("cn2", meta["collect_errors"])


if __name__ == "__main__":
    unittest.main()
