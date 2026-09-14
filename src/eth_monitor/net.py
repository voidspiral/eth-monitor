"""Parse Linux /proc/net/dev and select ethernet interfaces."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

ARPHRD_ETHER = 1
EXCLUDE_PATTERNS = (
    "lo",
    "ib*",
    "mlx*",
    "veth*",
    "docker*",
    "virbr*",
    "tun*",
    "tap*",
    "dummy*",
)


@dataclass(frozen=True)
class NetCounters:
    rx_bytes: int
    rx_packets: int
    tx_bytes: int
    tx_packets: int


def parse_net_dev(text: str) -> dict[str, NetCounters]:
    out: dict[str, NetCounters] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        name, rest = line.split(":", 1)
        iface = name.strip()
        if not iface or iface in {"face", "Inter-"}:
            continue
        parts = rest.split()
        if len(parts) < 10:
            continue
        try:
            rx_bytes = int(parts[0])
            rx_packets = int(parts[1])
            tx_bytes = int(parts[8])
            tx_packets = int(parts[9])
        except ValueError:
            continue
        out[iface] = NetCounters(
            rx_bytes=rx_bytes,
            rx_packets=rx_packets,
            tx_bytes=tx_bytes,
            tx_packets=tx_packets,
        )
    return out


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _excluded_name(iface: str) -> bool:
    lowered = iface.lower()
    return any(fnmatch.fnmatch(lowered, pat) for pat in EXCLUDE_PATTERNS)


def select_ifaces(
    counters: dict[str, NetCounters],
    *,
    sys_class_net: Path,
) -> list[str]:
    chosen: list[str] = []
    for iface in counters:
        if _excluded_name(iface):
            continue
        base = sys_class_net / iface
        type_text = _read_text(base / "type")
        oper = (_read_text(base / "operstate") or "").strip().lower()
        if type_text is None:
            continue
        try:
            type_id = int(type_text.strip().split()[0])
        except ValueError:
            continue
        if type_id != ARPHRD_ETHER or oper != "up":
            continue
        if (base / "master").exists():
            continue
        chosen.append(iface)
    return chosen
