# eth-monitor

独立的 HPC 作业伴生监控：按**节点以太网卡**采集 `rx`/`tx` 速率，写出 JSONL 时序，并可选生成 PNG 曲线。加上 `--match` 时，还会用 sock_diag 字节差记录匹配 PID 的 TCP 速率（仅采样时仍存活的套接字）。本仓库不是 ClusterHelm，也不是 mpi-monitor，更不是 nethogs/pcap 抓包。

[English README](README.md)

采集器跟着被包装的命令走：先启动、命令返回后（stop 文件）停止。计算节点不必预装本包；远程主机通过 SSH 下发内联 Python payload。

## 安装

```bash
pip install -e .
# 可选：出 PNG（需要 matplotlib）
pip install -e ".[plot]"
```

需要 Python 3.10+。无 matplotlib 时仍会写 JSONL，只是跳过 PNG。

## 包装作业（wrap）

`--hosts` **必填**。主机网卡始终采集。可选 `--match`：`/proc/<pid>/comm` 含该子串（大小写敏感）的进程会写 PID TCP 时序。`srun` 的 rank 不在登录节点 wrap 的进程树里，所以要用 `--match`，不要指望进程树。

```bash
eth-monitor wrap \
  --hosts cn1,cn2 \
  --output-dir ./runs \
  --interval 1.0 \
  --match app \
  -- \
  srun -n2 ./app
```

- 默认 `--interval` 为 `1.0` 秒。
- wrap 的退出码等于被包装命令的退出码。
- 本机短主机名和 `localhost` 走本地采集；其它主机名走 SSH（可用 `--ssh-user`、`--ssh-identity`）。

## 采集方式：sock_diag 字节差

主机以太网和进程 TCP 是两套计数器，不是同一条曲线，也不是把网卡流量按 PID 拆开。

**主机以太网**（`series/{host}_net.jsonl`）周期读 `/proc/net/dev`。速率 = 网卡累计 `rx`/`tx` 字节的两次采样差 / 间隔秒数。每个接口第一拍为 `0`。这是整块网卡（含帧头、其他进程、非 TCP），不是某个 PID。

**进程 TCP**（`series/{host}_pid{pid}_net.jsonl`，需要 `--match`）用 **sock_diag 字节差**，不抓包：

1. 用 `/proc/<pid>/comm` 子串匹配 PID。
2. 读 `/proc/<pid>/stat` 的 starttime，PID 复用视为新进程实例。
3. 从 `/proc/<pid>/fd` 收集 `socket:[inode]`。
4. 用 `NETLINK_SOCK_DIAG` / `INET_DIAG` dump 仍活着的 TCP（`tcp_info`），用 inode + cookie 标识套接字。
5. 多个匹配 PID 共享同一 inode 时，只归属**最小 PID**。
6. **每条仍存活的套接字单独做差**，再按进程求和。已知进程上新出现的套接字：本周期增量 = 当前累计字节。关闭的套接字丢掉状态（最后一段补不回），且不会把其他套接字的正增量抵消掉。
7. 速率 = `max(Δbytes, 0) / 单调时钟间隔`。每个进程实例第一拍为 `0`。

Tx 优先用 `tcp_info` 的 `bytes_sent`；老内核没有该字段时回退 `bytes_acked`，wrap 会在 `meta.json` 里记 `tcp_info_partial`。Rx 用 `bytes_received`。计算节点只需 `python3` 和 `/proc`，不依赖 `ss` 或 `nethogs`。

只统计**采样时仍存在的 TCP 套接字**。两次采样之间已经建连、传完、关闭的短连接，以及 UDP、InfiniBand/RDMA、以太/IP 头都不计入，所以 `tcp_*_bps` 通常小于 `eth_*_bps`。这是进程级 TCP 记账，不是嗅探器。

## 输出目录

```
{output-dir}/{run_id}/
  meta.json
  series/{host}_net.jsonl
  series/{host}_pid{pid}_net.jsonl
  charts/{host}_{iface}_eth_rx_bps.png
  charts/{host}_{iface}_eth_tx_bps.png
  charts/{host}_pid{pid}_tcp_rx_bps.png
  charts/{host}_pid{pid}_tcp_tx_bps.png
```

主机 JSONL 每行包含：`ts`、`host`、`iface`、`eth_rx_bps`、`eth_tx_bps`。有 `--match` 时 pid-net 每行包含：`ts`、`host`、`pid`、`comm`、`process_starttime_ticks`、`tcp_rx_bps`、`tcp_tx_bps`。纳入 up 的以太网（或 bond 主设备）；排除 loopback、IB、veth 和 bond slave。

## 其它命令

```bash
eth-monitor collect --output-dir DIR --stop-file FILE --host HOST [--match STR]
eth-monitor plot --run-dir DIR
eth-monitor remote-cmd -- collect --output-dir DIR --stop-file FILE --host HOST
eth-monitor probe
```

`remote-cmd` 打印一条 `base64 | python3` 命令，给未安装本包的计算节点用。

## 测试

```bash
python3 -m unittest discover -s tests
```
