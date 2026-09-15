## Context

See `proposal.md` for motivation. The package already wraps a command, samples
`/proc/net/dev` into `series/{host}_net.jsonl`, ships an inline SSH payload,
and plots host-ethernet PNGs. `plot.is_net_series` currently treats any
`*_net.jsonl` as host ethernet, which would mis-read pid-net files.

Constraints: Python 3.10+; stdlib first; matplotlib optional; compute nodes
may have no package install; no hardcoded home paths; TDD with `unittest`
(failing tests first). Collectors follow the wrapped command. ClusterHelm
control-plane code is not a design input.

## Goals / Non-Goals

**Goals:**

- Same collect process and stop file also sample matched PIDs' live TCP
  sockets via sock_diag and write `series/{host}_pid{pid}_net.jsonl`.
- Injectable `/proc` root and diag dump so unit tests never open netlink.
- Forward `--match` on local spawn and remote collect argv.
- Split plot dispatch: host `{host}_net.jsonl` vs `{host}_pid{pid}_net.jsonl`.

**Non-Goals:**

- pcap, nethogs, eBPF, UDP, IB, short-connection catch-up, `--pids`.
- Changing mpi-monitor or agent-sidecar in this change.

## Decisions

### 1. Implementation method: TDD

Write failing `unittest` cases first: fake `/proc` comm match and socket
inodes, inet_diag/`tcp_info` parse fixtures, collect_loop pid JSONL and
no-match skip, plot host vs pid split, wrap/CLI `--match` forwarding.
Then implement until tests pass. No live netlink in unit tests.

**Alternatives:** implement then test (rejected by repo convention).

### 2. PID selection is `--match` on comm

`srun` ranks on compute nodes are not children of wrap (login node) or of
the SSH collector. Match `/proc/<pid>/comm` with a case-sensitive substring.
Empty or omitted match skips pid sampling entirely.

**Alternatives:** wrap process tree (empty on multi-host jobs); scan all
PIDs (noisy); `--pids` (deferred).

### 3. Sock_diag in stdlib netlink, not `ss`

New `eth_monitor.sockdiag` dumps `AF_INET` and `AF_INET6` TCP via
`NETLINK_SOCK_DIAG`. Parse `inet_diag_msg` inode and `INET_DIAG_INFO`
(`tcp_info`). Tx counters: `tcpi_bytes_sent` when the struct is long
enough, else `tcpi_bytes_acked`. Rx: `tcpi_bytes_received`.
`eth_monitor.proc` walks `/proc/<pid>/fd` `socket:[inode]` and dedupes
inodes. Join inode → bytes; sum per PID; rate = `max(cur-prev,0)/elapsed`.
First sample per PID is 0.0. Inject `proc_root` and `diag_dump`.

If fallback is used, write `tcp_info_partial` in the collect output dir
and merge `tcp_info_partial: true` into wrap `meta.json`. Include that
marker in the remote tar alongside `collect.err`.

**Alternatives:** shell out to `ss` (iproute2 not guaranteed); pcap
(needs `CAP_NET_RAW`).

### 4. Same loop, separate JSONL

`collect_loop(..., match=None)` still writes host ethernet first, then
pid samples when match is set. Pid schema keys are independent of
`SAMPLE_KEYS`. Do not copy NIC bps into pid files.

**Alternatives:** second collector process (more SSH/stop-file churn).

### 5. Plot filename split

Host ethernet: files matching `{host}_net.jsonl` without `_pid` in the
name. Pid TCP: `{host}_pid{pid}_net.jsonl` →
`{host}_pid{pid}_tcp_{rx,tx}_bps.png`. Skip mpi-monitor-style
`{host}_pid{pid}.jsonl`.

**Alternatives:** keep `endswith("_net.jsonl")` (rejected: mixes schemas).

### 6. Wrap CLI

Add optional `--match` to `wrap` and `collect`. `SpawnLocal` and remote
payload argv pass it through. Hosts remain required. No match remains
backward compatible.

## Risks / Trade-offs

- [Short TCP connections vanish between samples] → Document; do not try
  to reconstruct closed sockets.
- [Rates < NIC bps] → Expected (headers, other tenants, non-TCP); README.
- [Other users' `/proc/<pid>/fd`] → Fail-soft; same-user job wrap is the
  supported path.
- [tcp_info layout by kernel] → Length-gated field offsets; fallback +
  `tcp_info_partial`.
- [High PID count] → Match keeps the scan small; no all-process dump.

## Migration Plan

Non-breaking CLI add. Existing wraps without `--match` unchanged. Update
README and `openspec/config.yaml` context. Tag after unittest passes.

## Open Questions

None. Sidecar live overlay remains out of this change.
