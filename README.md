# eth-monitor

[中文说明](README.zh.md)

Standalone HPC sidecar that samples **host ethernet** `rx`/`tx` rates, then
writes JSONL timeseries and optional PNG charts. With `--match` it also records
per-PID TCP rates from sock_diag byte deltas (live sockets only). It is not
ClusterHelm, not mpi-monitor, and not a packet sniffer (no nethogs/pcap).

Collectors follow the wrapped command: they start first and stop when the
command returns (stop file). Compute nodes do not need a prior install; remote
hosts get an inline Python payload over SSH.

## Install

```bash
pip install -e .
# optional PNG extra
pip install -e ".[plot]"
```

Requires Python 3.10+. Plotting uses matplotlib when the `plot` extra is
installed; without it, JSONL is still written.

## Wrap a job

`--hosts` is **required**. Host ethernet is always sampled. Optional `--match`
selects PIDs whose `/proc/<pid>/comm` contains that substring (case-sensitive)
and writes per-PID TCP series. Use `--match` for `srun` ranks; they are not
children of wrap on compute nodes.

```bash
eth-monitor wrap \
  --hosts cn1,cn2 \
  --output-dir ./runs \
  --interval 1.0 \
  --match app \
  -- \
  srun -n2 ./app
```

- Default `--interval` is `1.0` seconds.
- Exit status is the wrapped command's exit status.
- Local hostname (and `localhost`) runs the collector in-process; other names
  are reached with SSH (`--ssh-user`, `--ssh-identity` if needed).

## How sampling works

Host ethernet and per-PID TCP are two different counters. They are not the
same number, and PID rates are not a split of the NIC curve.

**Host ethernet** (`series/{host}_net.jsonl`) reads Linux `/proc/net/dev`
once per interval. Rates are byte deltas of the NIC's cumulative `rx`/`tx`
bytes, divided by elapsed seconds. The first sample for an iface is `0`.
This is the full interface (headers, other tenants, non-TCP), not a process.

**Per-PID TCP** (`series/{host}_pid{pid}_net.jsonl`, needs `--match`) uses
**sock_diag byte deltas**, not packet capture:

1. Match PIDs by `/proc/<pid>/comm` substring.
2. Read `/proc/<pid>/stat` starttime so a reused PID is a new instance.
3. Collect `socket:[inode]` links from `/proc/<pid>/fd`.
4. Dump live TCP sockets with `NETLINK_SOCK_DIAG` / `INET_DIAG` (`tcp_info`),
   keyed by inode plus kernel socket cookie.
5. If several matched PIDs share an inode, only the **lowest PID** owns it.
6. Difference **each live socket**, then sum. A new socket on a known process
   contributes its current cumulative bytes this interval. A closed socket is
   dropped (its last interval is lost) and does not cancel other sockets.
7. Rate = `max(delta, 0) / monotonic_elapsed`. The first sample for a process
   instance is `0`.

Tx prefers `tcp_info` `bytes_sent`; if that field is missing on older kernels,
it falls back to `bytes_acked` and wrap records `tcp_info_partial` in
`meta.json`. Rx uses `bytes_received`. Compute nodes need `python3` and
`/proc`, not `ss` or `nethogs`.

This only covers **TCP sockets that still exist at sample time**. Connections
that open, transfer, and close between samples, plus UDP, InfiniBand/RDMA, and
Ethernet/IP headers, are not counted, so `tcp_*_bps` is typically smaller than
`eth_*_bps`. It is process-level TCP accounting, not a sniffer.

## Output layout

```
{output-dir}/{run_id}/
  meta.json
  series/{host}_net.jsonl
  series/{host}_pid{pid}_net.jsonl
  charts/{host}_{iface}_eth_rx_bps.png
  charts/{host}_{iface}_eth_tx_bps.png
  charts/{host}_pid{pid}_tcp_rx_bps.png
  charts/{host}_pid{pid}_tcp_tx_bps.png
```

Host JSONL lines include `ts`, `host`, `iface`, `eth_rx_bps`, `eth_tx_bps`.
Pid-net lines include `ts`, `host`, `pid`, `comm`, `process_starttime_ticks`,
`tcp_rx_bps`, `tcp_tx_bps` when `--match` is set. Included interfaces are up
ethernet (or bond master) devices. Loopback, IB, veth, and bond slaves are
excluded.

## Other commands

```bash
eth-monitor collect --output-dir DIR --stop-file FILE --host HOST [--match STR]
eth-monitor plot --run-dir DIR
eth-monitor remote-cmd -- collect --output-dir DIR --stop-file FILE --host HOST
eth-monitor probe
```

`remote-cmd` prints a `base64 | python3` one-liner for nodes that do not have
this package installed.

## Tests

```bash
python3 -m unittest discover -s tests
```
