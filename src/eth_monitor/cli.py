"""eth-monitor CLI."""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

from eth_monitor.collect import run_collect
from eth_monitor.plot import plot_run
from eth_monitor.remote import remote_cmd
from eth_monitor.wrap import wrap


def _add_collect_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--stop-file", required=True, type=Path)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--host", default=socket.gethostname().split(".")[0])
    p.add_argument("--match")
    p.add_argument("--proc-net", type=Path, default=None)
    p.add_argument("--sys-class-net", type=Path, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eth-monitor", description="Host ethernet rx/tx monitor")
    sub = parser.add_subparsers(dest="cmd", required=True)

    wrap_p = sub.add_parser("wrap", help="start collectors, run a command, then stop and plot")
    wrap_p.add_argument("--hosts", required=True, help="comma-separated host list (required)")
    wrap_p.add_argument("--output-dir", required=True, type=Path)
    wrap_p.add_argument("--interval", type=float, default=1.0)
    wrap_p.add_argument("--match", help="optional /proc comm substring for pid TCP sampling")
    wrap_p.add_argument("--join-timeout", type=float, default=5.0)
    wrap_p.add_argument("--ready-timeout", type=float, default=30.0)
    wrap_p.add_argument("--ssh-user")
    wrap_p.add_argument("--ssh-identity")
    wrap_p.add_argument("--run-id")
    wrap_p.add_argument(
        "--plot",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="generate per-iface PNG charts (default: enabled)",
    )
    wrap_p.add_argument("command", nargs=argparse.REMAINDER)

    collect_p = sub.add_parser("collect", help="node-local collector")
    _add_collect_args(collect_p)

    plot_p = sub.add_parser("plot", help="plot JSONL series in a run directory")
    plot_p.add_argument("--run-dir", required=True, type=Path)

    remote_p = sub.add_parser("remote-cmd", help="print an inline collector payload")
    remote_p.add_argument("remote_argv", nargs=argparse.REMAINDER)

    sub.add_parser("probe", help="CLI hard gate: succeed if this package can run")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "wrap":
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            print("eth-monitor wrap: missing command after --", file=sys.stderr)
            return 2
        hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
        if not hosts:
            print("eth-monitor: --hosts is required", file=sys.stderr)
            return 2
        return wrap(
            command,
            hosts=hosts,
            output_dir=args.output_dir,
            interval=args.interval,
            match=args.match,
            join_timeout=args.join_timeout,
            ready_timeout=args.ready_timeout,
            ssh_user=args.ssh_user,
            ssh_identity=args.ssh_identity,
            run_id=args.run_id,
            plot=args.plot,
        )

    if args.cmd == "collect":
        return run_collect(
            output_dir=args.output_dir,
            stop_file=args.stop_file,
            interval=args.interval,
            host=args.host,
            match=args.match,
            proc_net=args.proc_net,
            sys_class_net=args.sys_class_net,
        )

    if args.cmd == "plot":
        plot_run(args.run_dir)
        return 0

    if args.cmd == "remote-cmd":
        extra = list(args.remote_argv)
        if extra and extra[0] == "--":
            extra = extra[1:]
        print(remote_cmd(extra or None))
        return 0

    if args.cmd == "probe":
        print("ok")
        return 0

    parser.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
