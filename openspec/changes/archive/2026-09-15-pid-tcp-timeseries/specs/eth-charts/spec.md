## ADDED Requirements

### Requirement: One PNG per host, pid, and TCP metric
From a run's pid-net JSONL series, the plot step SHALL write one PNG per sampled
PID for each of `tcp_rx_bps` and `tcp_tx_bps`. Filenames SHALL follow
`{host}_pid{pid}_tcp_rx_bps.png` and `{host}_pid{pid}_tcp_tx_bps.png` under
`charts/` in the run directory.

#### Scenario: Two charts for one pid
- **WHEN** a run directory contains pid-net JSONL for one host and pid and
  plotting succeeds
- **THEN** `charts/` contains PNGs named with that host, pid, and the two TCP
  metric suffixes

## MODIFIED Requirements

### Requirement: One PNG per host, iface, and metric
From a run's host-ethernet JSONL series, the plot step SHALL write one PNG per
sampled interface for each of `eth_rx_bps` and `eth_tx_bps`. Filenames SHALL
follow `{host}_{iface}_eth_rx_bps.png` and `{host}_{iface}_eth_tx_bps.png` under
`charts/` in the run directory. Host-ethernet plotting MUST only read files named
`{host}_net.jsonl` that do not contain `_pid`. Process-style `{host}_pid{pid}.jsonl`
and pid-net `{host}_pid{pid}_net.jsonl` files MUST NOT produce ethernet iface PNGs.

#### Scenario: Two charts for one interface
- **WHEN** a run directory contains net JSONL for one host and iface and
  plotting succeeds
- **THEN** `charts/` contains PNGs named with that host, iface, and the two
  metric suffixes

#### Scenario: Process JSONL is ignored
- **WHEN** `series/` also contains `{host}_pid{pid}.jsonl`
- **THEN** the plot step MUST NOT emit cpu/rss/io PNGs from those files

#### Scenario: Pid-net JSONL is not treated as host ethernet
- **WHEN** `series/` contains `{host}_pid{pid}_net.jsonl` with `tcp_rx_bps`
- **THEN** the plot step MUST NOT emit `{host}_{iface}_eth_*` charts from that file
