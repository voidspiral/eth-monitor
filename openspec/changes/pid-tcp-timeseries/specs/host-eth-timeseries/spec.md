## ADDED Requirements

### Requirement: Optional match does not change ethernet sampling
Host ethernet sampling SHALL continue without a process match string. Wrap and
collect MAY accept `--match` to enable pid-tcp sampling in the same collector.
Ethernet JSONL SHALL remain `series/{host}_net.jsonl` at host+iface granularity
and MUST NOT copy NIC counters into pid files. Wrap MUST NOT require `--match`.

#### Scenario: Wrap without match still writes host net JSONL
- **WHEN** the user wraps a command with `--hosts` and omits `--match`
- **THEN** host ethernet samples are written when counters are readable and no
  `series/{host}_pid{pid}_net.jsonl` files are required

#### Scenario: Wrap with match still writes host net JSONL
- **WHEN** the user wraps a command with `--hosts` and `--match`
- **THEN** host ethernet JSONL is still written in addition to any pid-net files
