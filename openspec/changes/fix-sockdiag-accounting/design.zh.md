## 背景

动机见 `proposal.md`。当前 `collect_loop` 先把某 PID 所有套接字字节加总再做差。
主机以太网采集不变。测试注入 `proc_root` 和 `diag_dump`。

## 目标 / 非目标

**目标：**

- 对每条仍存活的 TCP 套接字单独做差，再按进程实例求和。
- 用 `/proc/<pid>/stat` 的 `(pid, starttime_ticks)` 识别进程实例。
- 共享 inode 只归属匹配进程中最小 PID。
- 保持 pid-net 文件名；增加 `process_starttime_ticks`。
- PID TCP 间隔用可注入的单调时钟。

**非目标：**

- 补回两次采样之间已关闭套接字的字节。
- pcap、UDP、IB、ClusterHelm、改 mpi-monitor。

## 决策

### 1. 实现方法：TDD

先写失败用例：stat starttime 解析、共享 inode 归属、sock_diag cookie 与本机
字节序、按套接字差分、PID 复用、新套接字增量、关闭套接字隔离、单调时钟间隔。
再实现到全绿。单元测试不开真 netlink。

**备选：** 先实现再测（仓库约定拒绝）。

### 2. 套接字身份：inode + cookie

用 `inet_diag_sockid.idiag_cookie[2]` 防止 inode 复用。状态键为
`(pid, starttime_ticks, inode, cookie)`。缺 cookie 视为 `(0, 0)`。

**备选：** 只用 inode（拒绝：复用冲突）。

### 3. 进程身份：pid + starttime

`/proc/<pid>/stat` 从最后一个 `)` 之后切字段，避免 comm 空格/括号错位。
comm 后第 22 字段为 starttime。读不到则跳过该 PID。

**备选：** 只用 pid（拒绝：复用）；用 ctime（不如 starttime 稳）。

### 4. 共享 inode 归属最小匹配 PID

在匹配持有者中取 min(pid)。未匹配持有者忽略。过滤后再差分、再按实例求和。

**备选：** 每个持有者都计（重复）；共享不计（漏掉 fork MPI）。

### 5. 新套接字与关闭套接字

- 某实例第一拍：全部套接字速率 0，记下当前字节。
- 已知实例出现新套接字：增量 = 当前累计字节。
- 已知套接字：`max(当前 - 上次, 0)`。
- 关闭套接字：丢掉状态，不加负项。

PID TCP 间隔用 `monotonic_fn`（默认 `time.monotonic`）；JSONL `ts` 仍是快照后的
Unix epoch。

**备选：** 新套接字等到下一拍（重连低估）。

### 6. tcp_info 用本机字节序

64 位计数按 `sys.byteorder` 解。保留 `bytes_sent` / `bytes_acked` 回退。

## 风险 / 权衡

- [两次采样之间的短连接] → 仍然看不见；写进文档。
- [fork 后 exec 改 comm] → 可能不再匹配；预期如此。
- [套接字很多] → 每拍仍一次 dump；match 限制 PID。

## 迁移

JSONL 加法字段。忽略未知键的旧读取器仍可用。更新 README。unittest 通过后归档。

## 未决问题

无。
