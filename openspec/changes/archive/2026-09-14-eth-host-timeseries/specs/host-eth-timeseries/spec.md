## Purpose

Provides a standalone CLI that wraps an HPC job command, samples host ethernet
NIC receive and transmit rates on named compute hosts, and records those
timeseries until the wrapped command finishes.

## ADDED Requirements

### Requirement: Wrap command is the primary invocation
The CLI SHALL provide a wrap invocation that starts collectors on the listed
hosts, runs a caller-supplied command, stops collectors when that command
returns, and exits with the wrapped command's exit status. Wrap MUST NOT
require a process match string.

#### Scenario: Successful wrap of a short local command
- **WHEN** the user wraps a finite command with at least one listed host
- **THEN** the CLI runs the command to completion, writes JSONL samples for
  included ethernet interfaces on that host when counters are readable, stops
  collectors, and returns the command's exit code

#### Scenario: Wrapped command failure is preserved
- **WHEN** the wrapped command exits non-zero
- **THEN** the CLI still stops collectors and writes any samples collected, and
  the CLI exit code SHALL equal the wrapped command's exit code

### Requirement: Sampling is host-and-iface ethernet rates
The monitor SHALL sample ethernet NIC counters at host + iface granularity,
not process PIDs and not whole-node averages that mix InfiniBand. Hosts SHALL
come from CLI flags; the implementation MUST NOT hardcode user home
directories or hostnames.

#### Scenario: Two-host wrap
- **WHEN** wrap is given two hosts
- **THEN** samples include both hosts' included interfaces when those NICs were
  readable, each sample carrying `host` and `iface`

#### Scenario: Host list is explicit
- **WHEN** the user omits hosts
- **THEN** the CLI SHALL fail with a non-zero exit and an error on stderr
  instead of inventing a host list

### Requirement: Interface inclusion and exclusion
On each host the collector SHALL include interfaces whose sysfs type is
ethernet (`type=1`) and whose operstate is `up`. It MUST exclude loopback,
InfiniBand-named devices (`ib*`, `mlx*`), virtual ethernet (`veth*`,
`docker*`, `virbr*`, `tun*`, `tap*`, `dummy*`), and bonding slaves (devices
with a sysfs `master`). Bond master devices that meet the ethernet/up rules
MUST be included.

#### Scenario: Bond master is sampled, slaves are not
- **WHEN** a host has `bond0` up as ethernet and `eth0`/`eth1` as its slaves
- **THEN** JSONL samples include `bond0` and MUST NOT include `eth0` or `eth1`

#### Scenario: Loopback and InfiniBand are skipped
- **WHEN** `lo` and `ib0` are present
- **THEN** those ifaces MUST NOT appear in JSONL

### Requirement: JSONL timeseries schema
Each sample line SHALL be a JSON object with at least: `ts` (Unix epoch
seconds, float), `host`, `iface`, `eth_rx_bps`, `eth_tx_bps`. Files SHALL be
written under the run directory as `series/{host}_net.jsonl`. The first sample
for an iface SHALL report zero rates. Packet counters MAY be present as extra
fields and MUST NOT be required.

#### Scenario: Schema keys present
- **WHEN** at least one sample is written
- **THEN** every JSONL object contains the required keys and `eth_rx_bps` and
  `eth_tx_bps` are numbers

#### Scenario: One file per host
- **WHEN** two hosts are sampled
- **THEN** each host has its own `series/{host}_net.jsonl`; multiple ifaces on
  one host share that file as separate lines with the same `ts`

### Requirement: Collect loop stops on stop file
The collector SHALL sample until a stop file exists. It MUST NOT exit because
application PIDs disappeared. Missing `/proc/net/dev` or sysfs MUST be
fail-soft (no samples or empty file), not a crash of the wrapped command.

#### Scenario: Stop file ends collection
- **WHEN** the stop file is created while the collector is running
- **THEN** the collector exits without requiring matching PIDs

#### Scenario: Unreadable counters do not fail wrap
- **WHEN** ethernet counters cannot be read on a host
- **THEN** wrap still returns the wrapped command's exit code

### Requirement: Remote nodes need no package install
When a listed host is not the local machine, wrap SHALL start collection via
SSH using an inline payload so the remote node needs `python3` and `/proc`,
not a prior install of this package.

#### Scenario: Remote collect payload is printable
- **WHEN** the CLI is asked for a remote-cmd payload
- **THEN** it prints a `base64 | python3` command that can invoke collect
