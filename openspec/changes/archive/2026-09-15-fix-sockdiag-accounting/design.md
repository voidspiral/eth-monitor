## Context

See `proposal.md` for motivation. `collect_loop` currently sums all matched
socket byte counters per PID, then differences that sum. Host ethernet
sampling is unchanged. Tests inject `proc_root` and `diag_dump`.

## Goals / Non-Goals

**Goals:**

- Difference each live TCP socket, then sum per process instance.
- Identify instances with `(pid, starttime_ticks)` from `/proc/<pid>/stat`.
- Attribute a shared inode only to the lowest matched PID.
- Keep pid-net filenames; add `process_starttime_ticks`.
- Use injectable monotonic time for PID TCP elapsed.

**Non-Goals:**

- Recovering bytes from sockets that vanished between samples.
- pcap, UDP, IB, ClusterHelm, mpi-monitor edits.

## Decisions

### 1. Implementation method: TDD

Write failing unittest cases first for stat starttime parse, shared-inode
owner, sock_diag cookie and native-endian counters, per-socket deltas,
PID reuse, new-socket increment, closed-socket isolation, monotonic
elapsed. Then implement until tests pass. No live netlink in unit tests.

**Alternatives:** implement then test (rejected by repo convention).

### 2. Socket identity is inode plus cookie

`inet_diag_sockid.idiag_cookie[2]` distinguishes sockets if an inode is
reused. Previous state key is
`(pid, starttime_ticks, inode, cookie)`. Missing cookie parses as `(0, 0)`.

**Alternatives:** inode only (rejected: reuse collision).

### 3. Process identity is pid plus starttime

Parse `/proc/<pid>/stat` after the last `)` so comm spaces/parentheses do
not shift fields. Field 22 (1-based after comm) is starttime. Unreadable
stat skips the PID (fail-soft).

**Alternatives:** pid only (rejected: reuse); `/proc/<pid>` ctime (less
stable than starttime).

### 4. Lowest matched PID owns a shared inode

Build inode → min(pid) among matched holders. Unmatched holders are
ignored. After filtering, difference sockets, then sum by instance.

**Alternatives:** count for every holder (double counting); skip shared
(misses fork MPI).

### 5. New vs closed sockets

- First sample for an instance: all sockets rate 0, store current bytes.
- Known instance, new socket: increment = current cumulative bytes.
- Known socket: `max(current - previous, 0)`.
- Closed socket: drop state; do not add a negative term.

PID TCP elapsed uses `monotonic_fn` (default `time.monotonic`); JSONL `ts`
stays Unix epoch from `now_fn` taken after the TCP snapshot.

**Alternatives:** zero new sockets until the next tick (under-counts
reconnects that stay up).

### 6. Native endian tcp_info

Unpack 64-bit `tcp_info` counters with `sys.byteorder`. Keep
`bytes_sent` / `bytes_acked` fallback.

## Risks / Trade-offs

- [Short connections between samples] → Still invisible; document.
- [Fork then exec with new comm] → May drop match; expected.
- [High socket count] → Still one dump per tick; match limits PIDs.

## Migration Plan

Additive JSONL field. Existing readers that ignore unknown keys keep
working. Update README. Archive after unittest passes.

## Open Questions

None.
