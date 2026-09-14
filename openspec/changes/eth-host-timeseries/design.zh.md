## 背景

动机见 `proposal.md`。本仓目前只有包脚手架（`eth_monitor` CLI 仅 `probe`），还没有采集器。邻居仓 mpi-monitor 提供 wrap、SSH 内联 payload、stop 文件和可选 matplotlib 的模式，但 **不要** 沿用它的 JSONL 契约或 `--match`。ClusterHelm 控制面代码不是设计输入。

约束：Python 3.10+；优先标准库；matplotlib 可选；计算节点可能未安装本包；禁止硬编码家目录；用 `unittest` 做 TDD（先红测再实现）。采集器跟着被包装的命令走。`collect_loop` 必须能被后续的 agent-sidecar import。

## 目标 / 非目标

**目标：**

- 提供 `eth-monitor` CLI：`wrap`、`collect`、`plot`、`remote-cmd`、`probe`。
- 主机+网卡以太网 JSONL（`series/{host}_net.jsonl`）和可选 PNG。
- 可注入 proc/sysfs 根路径，单测不需要真实网卡。
- 非本机 `--hosts` 走 SSH 内联 payload。

**非目标：**

- InfiniBand、pcap、进程级 net、PMPI、live Chart.js、ClusterHelm 适配。
- 本 change 不改 mpi-monitor 或 agent-sidecar。

## 决策

### 1. 实现方法：TDD

先写失败的 `unittest`：`/proc/net/dev` 解析、iface 过滤（bond slave、lo、ib）、collect_loop 的 stop 文件、JSONL 契约、plot 跳过 pid 文件和缺 matplotlib、wrap 必填 hosts 与退出码透传。再实现直到测试通过。单测不走真网络；SSH wrap 用 fake。

**备选：** 先实现再补测试（被仓库约定否定）。

### 2. 包布局

```
src/eth_monitor/   # net 解析、collect_loop、plot、wrap、remote、cli
tests/             # unittest
pyproject.toml     # console script `eth-monitor`
```

`collect_loop(output_dir, stop_file, interval, host, ...)` 没有 `match`。
Proc 路径（`proc_net`、`sys_class_net`）可注入。

**备选：** 把网卡采样折进 mpi-monitor（否定：pid 契约）；在 agent-sidecar 里刮 `/proc/net`（否定：独立工具）。

### 3. 网卡选择

从 `/proc/net/dev` 读计数。门槛：`/sys/class/net/<iface>/type` == 1（ARPHRD_ETHER）、`operstate` == `up`、没有 `master` 文件（不是 bond slave），以及名字排除（`lo`、`ib*`、`mlx*`、`veth*`、`docker*`、`virbr*`、`tun*`、`tap*`、`dummy*`）。bond 主设备只采一次。

速率 = 字节差 / 时间差；第一个样本为 0.0。

**备选：** nethogs/pcap（需要 CAP_NET_RAW）；只用 sysfs statistics（等价，但 `/proc/net/dev` 是单文件）。

### 4. 每主机一个 JSONL

`series/{host}_net.jsonl`，每个采样时刻每块网卡一行（带 `iface` 字段）。sidecar 后续 live overlay 按 `(host, iface)` 分组。

**备选：** `{host}_{iface}.jsonl`（文件更多）；塞进 pid JSONL（否定）。

### 5. Wrap 与远程 payload

沿用 mpi-monitor 的 wrap/SSH/setsid 模式，但不写 ClusterHelm incident，也没有 `--match`。本机跑 `python3 -m eth_monitor collect`。远端用打包 zip 的内联 payload。wrap 退出码等于用户命令退出码；采集错误记入 `meta.json` 为 partial。

**备选：** 要求每台节点预装（否定）。

### 6. 出图分发

只 glob `*_net.jsonl`。不匹配的文件跳过。每块网卡两张 PNG。缺 matplotlib：警告、保留 JSONL、wrap 仍成功。

## 风险 / 权衡

- [MPI 走 IB 时以太网曲线接近 0] → README 写明；不要把 eth 为 0 当成通信空闲。
- [Bond 改名 / VLAN] → type=1 + up + 非 slave；若 `eth0.N` 是 up 可能出现，P0 可接受。
- [时钟回拨] → 把 elapsed 夹到 >= 0；首点为 0。
- [SSH 挂起] → 与 mpi-monitor 一样 BatchMode + ConnectTimeout。

## 迁移计划

新包。无生产迁移。unittest 通过后打标签。agent-sidecar 的 import 是那个仓库的后续 change。

## 未决问题

无。sidecar live overlay 明确不在本 change。
