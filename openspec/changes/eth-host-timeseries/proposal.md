## Why

HPC jobs need host-level ethernet rx/tx timeseries that a job-user sidecar can
sample without root, pcap, or process matching. Process-monitor JSONL is
host+pid and cannot hold NIC rates: Linux has no `/proc/<pid>/io` equivalent
for network bytes, and stuffing NIC counters into pid files would draw identical
curves per rank. This repo exists to collect ethernet rates as a standalone
deterministic CLI that agent-sidecar can later import.

## What Changes

- Add a Python CLI that wraps a user command, samples ethernet NIC counters on
  named hosts, writes JSONL timeseries, and optionally emits PNG charts.
- Sample at host+iface granularity, not per-pid. Include up ethernet and bond
  master devices; exclude loopback, InfiniBand, veth, and bond slaves.
- Reach compute nodes that do not have this package installed by sending an
  inline collector payload over SSH.
- Stop collectors when the wrapped command returns (stop file). No `--match`,
  and no exit-when-PIDs-disappear loop.

## Non-goals

- Not a ClusterHelm slave workflow, OpenCode skill, or `workflow_runner` hook.
  ClusterHelm control-plane integration is out of scope and must not be copied.
- Not an extension of mpi-monitor (process CPU/RSS/block IO, `{host}_pid{pid}.jsonl`).
- No InfiniBand/verbs port counters, nethogs, libpcap, or per-pid network bytes.
- No PMPI / `LD_PRELOAD`, no live Chart.js overlay (that lives in agent-sidecar),
  no Prometheus/Grafana, no node-resident daemon.
- No hardcoded user home paths. Hosts, output directory, and SSH options come
  from CLI flags.

## Capabilities

### New Capabilities

- `host-eth-timeseries`: wrap a command, sample host ethernet rx/tx rates,
  write `series/{host}_net.jsonl`, and stop with the job.
- `eth-charts`: emit independently named PNG curves (one file per host × iface
  × rx/tx metric) from net JSONL, with matplotlib optional.

### Modified Capabilities

- (none; this repository has no baseline specs yet)

## Impact

- **New package:** Python 3.10+ library and `eth-monitor` CLI under this repo.
- **Outputs:** per-run directory with `series/{host}_net.jsonl` and optional
  `charts/{host}_{iface}_eth_{rx,tx}_bps.png`.
- **Dependencies:** stdlib for collect/wrap; matplotlib optional for plots.
- **Operations:** SSH from the launch host to `--hosts`; inline remote payload
  so compute nodes need `python3` and `/proc`, not a prior install.
- **Neighbors:** mpi-monitor and agent-sidecar are reference-only; this change
  does not edit those trees.
