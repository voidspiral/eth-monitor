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
- PID TCP 只覆盖采样时仍活着的 TCP；短连接、UDP、IB 不计。数值是内核 TCP 载荷类计数，通常小于 `eth_*_bps`。

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

主机 JSONL 每行包含：`ts`、`host`、`iface`、`eth_rx_bps`、`eth_tx_bps`。有 `--match` 时 pid-net 每行包含：`ts`、`host`、`pid`、`comm`、`tcp_rx_bps`、`tcp_tx_bps`。纳入 up 的以太网（或 bond 主设备）；排除 loopback、IB、veth 和 bond slave。

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
