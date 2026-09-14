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
- PID TCP rates cover live TCP sockets at sample time. Short connections, UDP,
  and InfiniBand are not counted. Values are kernel TCP payload-class counters
  and are typically smaller than `eth_*_bps`.

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
Pid-net lines include `ts`, `host`, `pid`, `comm`, `tcp_rx_bps`, `tcp_tx_bps`
when `--match` is set. Included interfaces are up ethernet (or bond master)
devices. Loopback, IB, veth, and bond slaves are excluded.

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
