"""Command-line interface for py_aimio."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import aim_info, isq_info, scv_info


def _json_default(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _info_reader(path: str, file_format: str):
    if file_format == "aim":
        return aim_info
    if file_format == "isq":
        return isq_info
    if file_format == "scv":
        return scv_info
    if Path(path).suffix.lower() == ".scv":
        return scv_info
    if Path(path).suffix.lower() == ".isq":
        return isq_info
    return aim_info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aimio-info",
        description="Print AIM, ISQ, or SCV header metadata as JSON.",
    )
    parser.add_argument("path", help="Path to image file")
    parser.add_argument(
        "--format",
        choices=("auto", "aim", "isq", "scv"),
        default="auto",
        help="Input file format (default: auto from extension)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation level (default: 2)",
    )
    args = parser.parse_args(argv)

    info = _info_reader(args.path, args.format)(args.path)
    print(json.dumps(info, indent=args.indent, sort_keys=True, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
