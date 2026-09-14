"""eth-monitor CLI stub (collect/plot/wrap land in the first OpenSpec change)."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eth-monitor",
        description="Host ethernet rx/tx timeseries monitor",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe", help="CLI hard gate: succeed if this package can run")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "probe":
        print("ok")
        return 0
    parser.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
