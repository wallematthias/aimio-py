"""Command-line interface for py_aimio."""

from __future__ import annotations

import argparse
import json
from typing import Any

from . import image_info


def _json_default(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aimio-info",
        description="Print AIM, ISQ, SCV, or GOBJ header metadata as JSON.",
    )
    parser.add_argument("path", help="Path to image file")
    parser.add_argument(
        "--format",
        choices=("auto", "aim", "isq", "scv", "gobj"),
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

    info = image_info(args.path, format=args.format)
    print(json.dumps(info, indent=args.indent, sort_keys=True, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
