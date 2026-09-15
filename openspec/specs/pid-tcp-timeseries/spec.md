# pid-tcp-timeseries Specification

## Purpose
Samples per-process TCP receive and transmit rates on named compute hosts by
differencing live socket byte counters, so an HPC job wrap can record rank-level
TCP timeseries without packet capture.

## Requirements

### Requirement: Match string selects PIDs by comm substring
When `--match` is provided and non-empty, the collector SHALL include a PID if
`/proc/<pid>/comm` contains that string as a case-sensitive substring. It MUST
NOT select PIDs from the wrap command's process tree. Omitted or empty `--match`
MUST NOT write pid-net JSONL and MUST NOT scan all processes.

#### Scenario: Matching comm is sampled
- **WHEN** collect runs with `--match app` and a process whose comm contains `app` has readable TCP sockets
- **THEN** JSONL samples for that PID are written with `host`, `pid`, and `comm`

#### Scenario: Non-matching comm is ignored
- **WHEN** collect runs with `--match app` and only `sshd` and the collector itself are present
- **THEN** no pid-net JSONL files are written for those processes

#### Scenario: No match skips pid sampling
- **WHEN** collect runs without `--match`
- **THEN** the collector MUST NOT create `series/{host}_pid{pid}_net.jsonl`

### Requirement: JSONL timeseries is host plus pid
Each pid-net sample line SHALL be a JSON object with at least: `ts` (Unix epoch
seconds, float), `host`, `pid` (integer), `comm`, `process_starttime_ticks`
(integer, `/proc/<pid>/stat` starttime), `tcp_rx_bps`, `tcp_tx_bps`. Files SHALL
be written as `series/{host}_pid{pid}_net.jsonl`. The first sample for a process
instance SHALL report zero rates. Extra fields MAY be present.

#### Scenario: Schema keys present
- **WHEN** at least one pid-net sample is written
- **THEN** every JSONL object contains the required keys and `tcp_rx_bps` and
  `tcp_tx_bps` are numbers

#### Scenario: One file per host and pid
- **WHEN** two matching PIDs are sampled on one host
- **THEN** each PID has its own `series/{host}_pid{pid}_net.jsonl`

#### Scenario: Starttime is recorded
- **WHEN** a pid-net sample is written
- **THEN** `process_starttime_ticks` equals that process's `/proc/<pid>/stat`
  starttime field

### Requirement: Rates come from live TCP socket byte deltas
Rates SHALL be computed per live TCP socket (inode plus sock_diag cookie), then
summed for the owning process instance. Tx SHALL use `bytes_sent` when that
field is present in `tcp_info`; otherwise tx SHALL use `bytes_acked`. Sockets
that close between samples, UDP, and InfiniBand MUST NOT be counted. Missing
`/proc` or sock_diag MUST be fail-soft (no pid samples), not a crash of the
wrapped command. The elapsed time for PID TCP rates SHALL be monotonic clock
delta, not wall-clock jumps.

#### Scenario: Second sample is a positive byte delta
- **WHEN** a matched process instance's live TCP sent bytes increase on the same
  socket between two samples
- **THEN** that socket contributes `(delta_bytes / elapsed_seconds)` to
  `tcp_tx_bps`, with negative per-socket deltas clamped to zero

#### Scenario: Closed socket does not cancel remaining sockets
- **WHEN** one of several live sockets on a matched process closes and another
  socket's counters increase
- **THEN** `tcp_tx_bps` includes the remaining socket's positive delta and MUST
  NOT subtract the closed socket's previous cumulative bytes

#### Scenario: New socket on a known process is counted from its current bytes
- **WHEN** a process instance already has pid-net samples and a new live TCP
  socket appears with non-zero cumulative bytes
- **THEN** that period's rate includes those current bytes as the socket's
  increment

#### Scenario: Unreadable diag does not fail wrap
- **WHEN** sock_diag or `/proc/<pid>/fd` cannot be read
- **THEN** wrap still returns the wrapped command's exit code

### Requirement: Collect loop still stops on the stop file
Pid sampling SHALL run in the same collector as host ethernet, on the same
interval, until the stop file exists. Disappearing matched PIDs MUST NOT end
collection.

#### Scenario: PID exit does not stop collection
- **WHEN** a matched PID disappears while the stop file is absent
- **THEN** the collector continues until the stop file exists and MUST NOT
  require matching PIDs to remain

### Requirement: Match is forwarded to remote collectors
When wrap lists a non-local host and `--match` is set, the SSH collect payload
SHALL include that match string so remote nodes need `python3` and `/proc`,
not `ss` or a prior install of this package.

#### Scenario: Remote collect argv includes match
- **WHEN** wrap is given a remote host and `--match app`
- **THEN** the remote collect invocation includes `--match app`

### Requirement: Shared sockets are attributed to the lowest matched PID
When more than one matched PID holds the same TCP socket inode, the collector
SHALL attribute that socket only to the lowest numeric PID among those holders.
Unmatched processes that also hold the inode MUST NOT change this rule.

#### Scenario: Two matched PIDs share one socket
- **WHEN** PIDs 10 and 20 both match `--match` and share one live TCP socket
- **THEN** that socket's bytes appear only in PID 10's pid-net samples

### Requirement: PID reuse starts a new process instance
A process instance SHALL be identified by `(pid, process_starttime_ticks)`.
When a PID number is reused with a different starttime, the first sample for
the new instance SHALL report zero rates and MUST NOT difference against the
previous occupant.

#### Scenario: Reused PID first sample is zero
- **WHEN** PID 42 exits and a new matching process reuses PID 42
- **THEN** the first sample after reuse has `tcp_rx_bps` and `tcp_tx_bps` equal
  to 0.0 and a different `process_starttime_ticks` than the previous occupant
