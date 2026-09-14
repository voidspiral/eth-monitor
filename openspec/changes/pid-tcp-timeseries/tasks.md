## 1. Proc match and socket inodes

- [x] 1.1 Write failing tests for comm substring match, socket inode collection with dedupe, and unreadable PID skip; verify `python3 -m unittest tests.test_proc` fails
- [x] 1.2 Implement `eth_monitor.proc` with injectable `proc_root` and verify `python3 -m unittest tests.test_proc` passes

## 2. Sock_diag parse and byte rates

- [x] 2.1 Write failing tests for inet_diag/`tcp_info` parse (IPv4/IPv6, `bytes_sent` vs short-struct `bytes_acked` fallback) and per-inode byte maps; verify `python3 -m unittest tests.test_sockdiag` fails
- [x] 2.2 Implement `eth_monitor.sockdiag` dump/parse with injectable `diag_dump` and verify `python3 -m unittest tests.test_sockdiag` passes

## 3. Collect loop pid JSONL

- [x] 3.1 Write failing tests: with `--match` writes `series/{host}_pid{pid}_net.jsonl` schema and zero first sample; without match writes no pid files; stop file still exits immediately; verify `python3 -m unittest tests.test_collect` fails
- [x] 3.2 Extend `collect_loop` / `run_collect` with optional `match`, pid sampling in the same loop, and `tcp_info_partial` marker; verify `python3 -m unittest tests.test_collect` passes

## 4. Plot split

- [x] 4.1 Write failing tests that `{host}_pid{pid}_net.jsonl` yields `{host}_pid{pid}_tcp_{rx,tx}_bps.png` and is not treated as host ethernet; existing host charts still pass; verify `python3 -m unittest tests.test_plot` fails
- [ ] 4.2 Update `eth_monitor.plot` filename dispatch and verify `python3 -m unittest tests.test_plot` passes

## 5. CLI wrap / SSH match

- [ ] 5.1 Write failing tests that wrap/collect accept `--match` and forward it to local spawn and remote collect argv; omit match keeps previous behavior; verify `python3 -m unittest tests.test_cli tests.test_wrap` fails
- [ ] 5.2 Implement CLI/wrap/remote tar marker merge into `meta.json` and verify `python3 -m unittest tests.test_cli tests.test_wrap` passes

## 6. Docs and full suite

- [ ] 6.1 Update README.md / README.zh.md and `openspec/config.yaml` context for optional `--match` and pid-net accuracy; verify `python3 -m unittest discover -s tests` passes
