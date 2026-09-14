# eth-charts Specification

## Purpose
Turns host-ethernet JSONL timeseries into independently named PNG charts, one
file per sampled interface and rx/tx metric, so operators can inspect
ethernet curves after an HPC job without embedding binaries in reports.

## Requirements

### Requirement: One PNG per host, iface, and metric
From a run's net JSONL series, the plot step SHALL write one PNG per sampled
interface for each of `eth_rx_bps` and `eth_tx_bps`. Filenames SHALL follow
`{host}_{iface}_eth_rx_bps.png` and `{host}_{iface}_eth_tx_bps.png` under
`charts/` in the run directory. Process-style `{host}_pid{pid}.jsonl` files
MUST be skipped.

#### Scenario: Two charts for one interface
- **WHEN** a run directory contains net JSONL for one host and iface and
  plotting succeeds
- **THEN** `charts/` contains PNGs named with that host, iface, and the two
  metric suffixes

#### Scenario: Process JSONL is ignored
- **WHEN** `series/` also contains `{host}_pid{pid}.jsonl`
- **THEN** the plot step MUST NOT emit cpu/rss/io PNGs from those files

### Requirement: Charts are time series of the sampled metric
Each PNG SHALL plot sample time on the x-axis and the corresponding metric on
the y-axis (`eth_rx_bps`, `eth_tx_bps`). Empty series MUST skip that iface
and report the skip.

#### Scenario: Empty series skips that iface
- **WHEN** a net series file exists but contains no valid samples
- **THEN** the plot step MUST NOT emit charts for that file and MUST report
  the skip

### Requirement: Plotting is optional when matplotlib is missing
If matplotlib is not importable, the plot step SHALL leave JSONL in place,
emit a warning on stderr, skip PNG creation, and MUST NOT fail the wrap solely
because plots could not be drawn.

#### Scenario: JSONL retained without matplotlib
- **WHEN** wrap completes sampling but matplotlib cannot be imported
- **THEN** series JSONL remains on disk, no PNG is required, and wrap still
  returns the wrapped command's exit code
