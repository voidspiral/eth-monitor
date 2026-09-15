## Why

HPC jobs already get host-ethernet NIC rates, but operators still cannot tell
which rank is filling a TCP path. Linux has no `/proc/<pid>/io` equivalent for
network bytes, so this change adds process-level TCP rates from sock_diag
byte deltas without pcap, nethogs, or root.

## What Changes

- Add optional `--match` on wrap and collect. When set, the same collector
  also samples matching PIDs' live TCP sockets via INET_DIAG/`tcp_info` and
  writes `series/{host}_pid{pid}_net.jsonl`.
- Without `--match`, host ethernet behavior stays the same: only
  `series/{host}_net.jsonl`, no process scan.
- Plot host-ethernet JSONL only from `{host}_net.jsonl` (not `*_pid*_net.jsonl`).
  Emit optional PID TCP PNGs from pid-net JSONL.
- Record TCP `tcp_info` fallback (`bytes_sent` vs `bytes_acked`) in `meta.json`
  when the kernel struct is short.

## Non-goals

- Not a ClusterHelm slave workflow, OpenCode skill, or `workflow_runner` hook.
  ClusterHelm control-plane integration is out of scope and must not be copied.
- Not nethogs, libpcap, eBPF, promiscuous sniffing, or `CAP_NET_RAW`.
- Not UDP, InfiniBand/RDMA/verbs, short-connection catch-up after close, or
  stuffing NIC counters into pid files.
- Not wrapping-process-tree PID selection (ranks under `srun` are not wrap
  children on compute nodes). No `--pids` list in this change.
- Not an extension of mpi-monitor CPU/RSS/block IO JSONL. Do not edit that tree.
- No PMPI / `LD_PRELOAD`, live Chart.js, Prometheus/Grafana, or node daemon.
- No hardcoded user home paths. Hosts, match, output directory, and SSH options
  come from CLI flags.

## Capabilities

### New Capabilities

- `pid-tcp-timeseries`: when `--match` is set, sample per-PID TCP rx/tx rates
  from sock_diag byte deltas and write `series/{host}_pid{pid}_net.jsonl`.

### Modified Capabilities

- `host-eth-timeseries`: wrap/collect MAY accept optional `--match` to enable
  the pid-tcp path in the same collector; host ethernet sampling MUST still
  work without `--match` and MUST NOT require process matching.
- `eth-charts`: host-ethernet PNGs MUST ignore `{host}_pid{pid}_net.jsonl`;
  pid-net JSONL SHALL produce `{host}_pid{pid}_tcp_{rx,tx}_bps.png`.

## Impact

- **Package:** `eth_monitor` collect/wrap/cli/plot plus new `proc` and
  `sockdiag` modules. Remote zip payload picks up new `.py` files automatically.
- **Outputs:** additional `series/{host}_pid{pid}_net.jsonl` and optional
  `charts/{host}_pid{pid}_tcp_{rx,tx}_bps.png` when `--match` is set.
- **Dependencies:** still stdlib for collect (netlink + `/proc`); matplotlib
  optional for plots. Compute nodes need `python3` and `/proc`, not `ss`.
- **Operations:** same SSH inline payload and stop-file lifecycle; `--match`
  is forwarded on local spawn and remote collect argv.
- **Accuracy:** rates cover live TCP sockets at sample time only; they are
  kernel TCP payload-class counters and are systematically smaller than
  `eth_*_bps`.
