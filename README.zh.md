# eth-monitor

独立的 HPC 作业伴生监控：按**节点以太网卡**采集 `rx`/`tx` 速率，写出 JSONL 时序，并可选生成 PNG 曲线。本仓库不是 ClusterHelm，也不是 mpi-monitor，更不是进程级抓包。

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

`--hosts` **必填**。没有 `--match`：本工具采的是主机网卡，不是 PID。

```bash
eth-monitor wrap \
  --hosts cn1,cn2 \
  --output-dir ./runs \
  --interval 1.0 \
  -- \
  srun -n2 ./app
```

- 默认 `--interval` 为 `1.0` 秒。
- wrap 的退出码等于被包装命令的退出码。
- 本机短主机名和 `localhost` 走本地采集；其它主机名走 SSH（可用 `--ssh-user`、`--ssh-identity`）。

## 输出目录

```
{output-dir}/{run_id}/
  meta.json
  series/{host}_net.jsonl
  charts/{host}_{iface}_eth_rx_bps.png
  charts/{host}_{iface}_eth_tx_bps.png
```

JSONL 每行包含：`ts`、`host`、`iface`、`eth_rx_bps`、`eth_tx_bps`。纳入 up 的以太网（或 bond 主设备）；排除 loopback、IB、veth 和 bond slave。

## 其它命令

```bash
eth-monitor collect --output-dir DIR --stop-file FILE --host HOST
eth-monitor plot --run-dir DIR
eth-monitor remote-cmd -- collect --output-dir DIR --stop-file FILE --host HOST
eth-monitor probe
```

`remote-cmd` 打印一条 `base64 | python3` 命令，给未安装本包的计算节点用。

## 测试

```bash
python3 -m unittest discover -s tests
```
