## Why

Per-PID TCP rates currently difference summed byte counters for a PID. When
sockets open or close between samples, that sum can drop and the period is
clamped to zero, hiding remaining live traffic. PID reuse and shared inodes
after fork also mis-attribute rates.

## What Changes

- Differ live TCP sockets individually, then sum those deltas per PID.
- Identify a process as `(pid, /proc/<pid>/stat starttime)`. A reused PID
  starts at zero rates again.
- When several matched PIDs hold the same socket, attribute it only to the
  lowest PID.
- Add `process_starttime_ticks` to pid-net JSONL. Keep
  `series/{host}_pid{pid}_net.jsonl`.
- Use monotonic time as the rate denominator for PID TCP samples.
- Document socket-level accounting and remaining short-connection limits.

## Non-goals

- Not a ClusterHelm slave workflow, OpenCode skill, or `workflow_runner` hook.
  ClusterHelm control-plane integration is out of scope and must not be copied.
- Not pcap, nethogs, eBPF, UDP, InfiniBand/RDMA, or reconstructing bytes from
  sockets that closed between samples.
- Not changing host-ethernet `/proc/net/dev` sampling.
- Not changing mpi-monitor or agent-sidecar.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `pid-tcp-timeseries`: socket-level byte deltas, process starttime identity,
  lowest-PID ownership of shared sockets, and `process_starttime_ticks` on
  samples.

## Impact

- **Package:** `eth_monitor.proc`, `eth_monitor.sockdiag`, `eth_monitor.collect`,
  pid-net JSONL schema, README.
- **Outputs:** same pid-net filenames; each sample gains
  `process_starttime_ticks`.
- **Dependencies:** still stdlib netlink and `/proc`.
- **Accuracy:** live long-lived TCP is more robust across reconnects; sockets
  that exist only between samples remain invisible.
