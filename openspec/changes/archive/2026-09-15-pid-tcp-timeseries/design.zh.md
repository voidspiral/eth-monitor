## 背景

动机见 `proposal.md`。本包已经能包装命令、从 `/proc/net/dev` 写
`series/{host}_net.jsonl`、经 SSH 下发内联 payload，并绘制主机以太网 PNG。
当前 `plot.is_net_series` 把任何 `*_net.jsonl` 都当成网卡文件，pid-net
会被误读。

约束：Python 3.10+；标准库优先；matplotlib 可选；计算节点可不预装本包；
禁止写死家目录；TDD（`unittest`，先失败用例）。采集器跟着被包装命令走。
ClusterHelm 控制面代码不是设计输入。

## 目标 / 非目标

**目标：**

- 同一 collect 进程和 stop 文件，额外按匹配 PID 用 sock_diag 采活着的 TCP
  套接字，写出 `series/{host}_pid{pid}_net.jsonl`。
- `/proc` 根和 diag dump 可注入，单元测试不开 netlink。
- 本机 spawn 与远程 collect 参数透传 `--match`。
- 绘图分流：主机 `{host}_net.jsonl` 与 `{host}_pid{pid}_net.jsonl`。

**非目标：**

- pcap、nethogs、eBPF、UDP、IB、短连接补末段、`--pids`。
- 本变更不改 mpi-monitor 或 agent-sidecar。

## 决策

### 1. 实现方法：TDD

先写失败用例：假 `/proc` 的 comm 匹配与 socket inode、inet_diag/`tcp_info`
解析夹具、collect_loop 的 pid JSONL 与无 match 跳过、plot 分流、wrap/CLI
透传 `--match`。再实现到全绿。单元测试不访问真 netlink。

**备选：** 先实现再测（仓库约定拒绝）。

### 2. PID 选定用 `--match` 匹配 comm

计算节点上的 `srun` rank 不是登录节点 wrap、也不是 SSH 采集器的子进程。
对 `/proc/<pid>/comm` 做大小写敏感子串匹配。空或省略 match 则完全不采 pid。

**备选：** wrap 进程树（多机作业为空）；扫全部 PID（噪声）；`--pids`（推迟）。

### 3. 标准库 netlink sock_diag，不用 `ss`

新模块 `eth_monitor.sockdiag` 经 `NETLINK_SOCK_DIAG` dump `AF_INET` 与
`AF_INET6` 的 TCP。解析 `inet_diag_msg` 的 inode 和 `INET_DIAG_INFO`
（`tcp_info`）。Tx：结构体够长用 `tcpi_bytes_sent`，否则 `tcpi_bytes_acked`。
Rx：`tcpi_bytes_received`。`eth_monitor.proc` 扫 `/proc/<pid>/fd` 的
`socket:[inode]` 并去重。按 inode 连接字节，按 PID 求和，速率
`max(cur-prev,0)/elapsed`。每个 PID 第一拍为 0.0。注入 `proc_root` 与
`diag_dump`。

若走了回退，在 collect 输出目录写 `tcp_info_partial`，并合并进 wrap 的
`meta.json`（`tcp_info_partial: true`）。远程 tar 里与 `collect.err` 一起带上
该标记。

**备选：** 调用 `ss`（不保证有 iproute2）；pcap（需要 `CAP_NET_RAW`）。

### 4. 同一循环，JSONL 分开

`collect_loop(..., match=None)` 仍先写主机以太网，有 match 再写 pid。
Pid 字段与网卡 `SAMPLE_KEYS` 分开。禁止把网卡 bps 写入 pid 文件。

**备选：** 第二个采集进程（更多 SSH/stop-file 协调）。

### 5. 绘图文件名分流

主机以太网：文件名是 `{host}_net.jsonl` 且不含 `_pid`。Pid TCP：
`{host}_pid{pid}_net.jsonl` → `{host}_pid{pid}_tcp_{rx,tx}_bps.png`。
跳过 mpi-monitor 风格的 `{host}_pid{pid}.jsonl`。

**备选：** 继续 `endswith("_net.jsonl")`（拒绝：会混 schema）。

### 6. Wrap CLI

`wrap` 与 `collect` 增加可选 `--match`。`SpawnLocal` 和远程 payload argv
透传。`--hosts` 仍必填。无 match 保持向后兼容。

## 风险 / 权衡

- [短 TCP 连接在两次采样之间消失] → 文档说明；不重建已关闭套接字。
- [速率小于网卡 bps] → 预期（头开销、其他租户、非 TCP）；写 README。
- [读不了其他用户的 `/proc/<pid>/fd`] → fail-soft；支持同一用户 wrap 作业。
- [不同内核 tcp_info 布局] → 按长度取字段；回退 + `tcp_info_partial`。
- [PID 很多] → 用 match 限制扫描；不全机 dump。

## 迁移

CLI 非破坏性增加。现有不加 `--match` 的 wrap 不变。更新 README 和
`openspec/config.yaml` 的 context。unittest 通过后打 tag。

## 未决问题

无。Sidecar 实时叠加仍不在本变更内。
