## 1. Parse `/proc/net/dev` and iface filter

- [x] 1.1 Write failing tests for `/proc/net/dev` parse and iface inclusion (ethernet up, bond master) versus exclusion (lo, ib*, mlx*, veth*, docker*, bond slaves); verify `python3 -m unittest tests.test_net_parse` fails
- [x] 1.2 Implement `eth_monitor.net` parse + filter with injectable sysfs/proc paths and verify `python3 -m unittest tests.test_net_parse` passes

## 2. Collect loop and JSONL

- [x] 2.1 Write failing tests for `collect_loop`: stop-file exit, first-sample zero rates, `series/{host}_net.jsonl` schema (`ts`, `host`, `iface`, `eth_rx_bps`, `eth_tx_bps`), one file per host; verify `python3 -m unittest tests.test_collect` fails
- [x] 2.2 Implement `eth_monitor.collect` (`collect_loop` / `run_collect`, no `--match`) and verify `python3 -m unittest tests.test_collect` passes

## 3. Optional PNG charts

- [x] 3.1 Write failing tests that net JSONL produces `{host}_{iface}_eth_rx_bps.png` and `_eth_tx_bps.png`, pid-style JSONL is skipped, missing matplotlib warns and leaves JSONL; verify `python3 -m unittest tests.test_plot` fails
- [x] 3.2 Implement `eth_monitor.plot` with injectable writer and verify `python3 -m unittest tests.test_plot` passes

## 4. CLI wrap / collect / remote-cmd

- [x] 4.1 Write failing tests: wrap without `--hosts` exits non-zero; wrap preserves command exit code; `remote-cmd` prints a decodable payload; `probe` prints ok; verify `python3 -m unittest tests.test_cli` fails
- [x] 4.2 Implement `cli`, `wrap`, and `remote` (SSH inline payload, no ClusterHelm) and verify `python3 -m unittest tests.test_cli tests.test_wrap` passes

## 5. Docs and full suite

- [x] 5.1 Update README.md / README.zh.md for wrap/collect/plot output layout and verify `python3 -m unittest discover -s tests` passes
