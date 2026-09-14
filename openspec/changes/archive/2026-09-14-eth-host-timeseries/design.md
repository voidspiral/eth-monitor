## Context

See `proposal.md` for motivation. This repository currently has a package
scaffold (`eth_monitor` CLI probe only) and no collector. Neighbor tree
mpi-monitor is the process collect/plot pattern to follow for wrap, SSH
inline payload, stop files, and optional matplotlib — not for JSONL schema
or `--match`. ClusterHelm control-plane code is not a design input.

Constraints: Python 3.10+; stdlib first; matplotlib optional; compute nodes
may have no package install; no hardcoded home paths; TDD with `unittest`
(failing tests first, then implementation). Collectors follow the wrapped
command. `collect_loop` must be importable by agent-sidecar later.

## Goals / Non-Goals

**Goals:**

- Package `eth-monitor` CLI: `wrap`, `collect`, `plot`, `remote-cmd`, `probe`.
- Host+iface ethernet JSONL (`series/{host}_net.jsonl`) and optional PNG.
- Injectable proc/sysfs roots so unit tests never need a live NIC.
- Remote inline payload over SSH for non-local `--hosts`.

**Non-Goals:**

- InfiniBand, pcap, per-pid net, PMPI, live Chart.js, ClusterHelm adapters.
- Changing mpi-monitor or agent-sidecar in this change.

## Decisions

### 1. Implementation method: TDD

Write failing `unittest` cases first: `/proc/net/dev` parse, iface filter
(bond slave, lo, ib), collect_loop stop-file, JSONL schema, plot skip of
pid files and missing matplotlib, wrap hosts-required and exit-code
passthrough. Then implement until tests pass. No network in unit tests;
SSH wrap is exercised with fakes.

**Alternatives:** implement then test (rejected by repo convention).

### 2. Package layout

```
src/eth_monitor/   # net parse, collect_loop, plot, wrap, remote, cli
tests/             # unittest
pyproject.toml     # console script `eth-monitor`
```

`collect_loop(output_dir, stop_file, interval, host, ...)` has no `match`.
Proc paths (`proc_net`, `sys_class_net`) are injectable.

**Alternatives:** folding net sampling into mpi-monitor (rejected: pid
contract); scraping `/proc/net` inside agent-sidecar (rejected: independent
tool).

### 3. Interface selection

Read counters from `/proc/net/dev`. Gate on `/sys/class/net/<iface>/type`
== 1 (ARPHRD_ETHER), `operstate` == `up`, no `master` file (not a bond
slave), and name exclusions (`lo`, `ib*`, `mlx*`, `veth*`, `docker*`,
`virbr*`, `tun*`, `tap*`, `dummy*`). Bond master is sampled once.

Rates = delta bytes / delta seconds; first sample is 0.0.

**Alternatives:** nethogs/pcap (needs CAP_NET_RAW); sysfs statistics only
(equivalent, but `/proc/net/dev` is one file).

### 4. JSONL one file per host

`series/{host}_net.jsonl` with one JSON object per iface per tick (`iface`
field). Live overlay (sidecar, later) groups by `(host, iface)`.

**Alternatives:** `{host}_{iface}.jsonl` (more files); stuffing into pid
JSONL (rejected).

### 5. Wrap and remote payload

Copy mpi-monitor wrap/SSH/setsid pattern without ClusterHelm incident
files and without `--match`. Local host runs `python3 -m eth_monitor collect`.
Remote uses zip-of-package inline payload. Wrap exit code is the user
command's exit code; collect errors are recorded in `meta.json` as partial.

**Alternatives:** require a deployed install on every node (rejected).

### 6. Plot dispatch

Only glob `*_net.jsonl`. Skip files that do not match. Two PNGs per iface.
Missing matplotlib: warn, keep JSONL, wrap still succeeds.

## Risks / Trade-offs

- [Ethernet-only curves look idle while MPI runs on IB] → Document in README;
  do not treat zero eth as communication idle.
- [Bond rename / VLAN] → type=1 + up + not slave; VLAN `eth0.N` may appear if
  up; acceptable for P0.
- [Clock jumps] → clamp elapsed to >= 0; first sample 0.
- [SSH hang] → BatchMode + ConnectTimeout like mpi-monitor.

## Migration Plan

New package. No production migration. Tag after unittest passes. agent-sidecar
import is a later change in that repo.

## Open Questions

None. Sidecar live overlay is explicitly out of this change.
