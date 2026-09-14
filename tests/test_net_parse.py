"""Parse /proc/net/dev and include/exclude ethernet ifaces."""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import tempfile
import unittest
from pathlib import Path

from eth_monitor.net import parse_net_dev, select_ifaces


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sysfs(root: Path, iface: str, *, type_id: str, operstate: str, master: str | None = None) -> None:
    base = root / iface
    _write(base / "type", type_id + "\n")
    _write(base / "operstate", operstate + "\n")
    if master is not None:
        (base / "master").symlink_to(root / master)


NET_DEV = """\
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 111 1 0 0 0 0 0 0 111 1 0 0 0 0 0 0
  eth0: 1000 10 0 0 0 0 0 0 2000 20 0 0 0 0 0 0
  eth1: 3000 30 0 0 0 0 0 0 4000 40 0 0 0 0 0 0
 bond0: 4000 40 0 0 0 0 0 0 6000 60 0 0 0 0 0 0
   ib0: 9999 9 0 0 0 0 0 0 8888 8 0 0 0 0 0 0
  mlx5_0: 1 1 0 0 0 0 0 0 1 1 0 0 0 0 0 0
  veth0: 5 1 0 0 0 0 0 0 5 1 0 0 0 0 0 0
docker0: 6 1 0 0 0 0 0 0 6 1 0 0 0 0 0 0
"""


class TestParseNetDev(unittest.TestCase):
    def test_parses_rx_tx_bytes(self) -> None:
        counters = parse_net_dev(NET_DEV)
        self.assertEqual(counters["eth0"].rx_bytes, 1000)
        self.assertEqual(counters["eth0"].tx_bytes, 2000)
        self.assertEqual(counters["eth0"].rx_packets, 10)
        self.assertEqual(counters["lo"].rx_bytes, 111)

    def test_skips_header_lines(self) -> None:
        counters = parse_net_dev(NET_DEV)
        self.assertNotIn("face", counters)
        self.assertNotIn("Inter-", counters)


class TestSelectIfaces(unittest.TestCase):
    def test_bond_master_included_slaves_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sys_root = Path(tmp) / "sys"
            _sysfs(sys_root, "bond0", type_id="1", operstate="up")
            _sysfs(sys_root, "eth0", type_id="1", operstate="up", master="bond0")
            _sysfs(sys_root, "eth1", type_id="1", operstate="up", master="bond0")
            names = select_ifaces(parse_net_dev(NET_DEV), sys_class_net=sys_root)
            self.assertEqual(names, ["bond0"])

    def test_plain_ethernet_up_included(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sys_root = Path(tmp) / "sys"
            _sysfs(sys_root, "eth0", type_id="1", operstate="up")
            names = select_ifaces(parse_net_dev(NET_DEV), sys_class_net=sys_root)
            self.assertEqual(names, ["eth0"])

    def test_excludes_lo_ib_veth_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sys_root = Path(tmp) / "sys"
            for name, typ in (
                ("lo", "772"),
                ("ib0", "32"),
                ("mlx5_0", "32"),
                ("veth0", "1"),
                ("docker0", "1"),
                ("eth0", "1"),
            ):
                _sysfs(sys_root, name, type_id=typ, operstate="up")
            names = select_ifaces(parse_net_dev(NET_DEV), sys_class_net=sys_root)
            self.assertEqual(names, ["eth0"])

    def test_down_ethernet_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sys_root = Path(tmp) / "sys"
            _sysfs(sys_root, "eth0", type_id="1", operstate="down")
            names = select_ifaces(parse_net_dev(NET_DEV), sys_class_net=sys_root)
            self.assertEqual(names, [])


if __name__ == "__main__":
    unittest.main()
