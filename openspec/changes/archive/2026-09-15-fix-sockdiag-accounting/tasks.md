## 1. Process identity and shared owners

- [x] 1.1 Write failing tests for `/proc/<pid>/stat` starttime (comm with spaces/parentheses), unreadable stat skip, and lowest-PID owner of a shared inode; verify `python3 -m unittest tests.test_proc` fails
- [x] 1.2 Implement `eth_monitor.proc` starttime parse and shared-inode owner map; verify `python3 -m unittest tests.test_proc` passes

## 2. Sock_diag cookie and endian

- [x] 2.1 Write failing tests for inet_diag cookie parse and native-endian `tcp_info` 64-bit counters; verify `python3 -m unittest tests.test_sockdiag` fails
- [x] 2.2 Implement cookie on `TcpBytes` and native-endian unpack; verify `python3 -m unittest tests.test_sockdiag` passes

## 3. Socket-level collect deltas

- [x] 3.1 Write failing tests: per-socket deltas, new socket increment, closed socket isolation, PID reuse zero, lowest-PID share, monotonic elapsed, `process_starttime_ticks`; verify `python3 -m unittest tests.test_collect` fails
- [x] 3.2 Implement `collect_loop` socket-level state, starttime identity, monotonic PID elapsed; verify `python3 -m unittest tests.test_collect` passes

## 4. Docs, archive, full suite

- [x] 4.1 Update README.md / README.zh.md sock_diag design section; verify `python3 -m unittest discover -s tests` and `openspec validate --specs` after syncing/archiving this change
