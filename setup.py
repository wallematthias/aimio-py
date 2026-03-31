from pathlib import Path
import sys

from setuptools import Extension, setup

ROOT = Path(__file__).resolve().parent
AIMIO_ROOT = ROOT / "external" / "AimIO"
N88UTIL_ROOT = ROOT / "external" / "n88util"
GENERATED_HEADERS_DIR = ROOT / "build_support" / "generated_headers"

SKIP_SOURCE_FILES = {"aix.cxx", "ctheader.cxx"}


def _require_dir(path: Path, label: str) -> None:
    if not path.is_dir():
        raise RuntimeError(
            f"Missing required directory '{path}'. Ensure git submodules are initialized for {label}:\n"
            "  git submodule update --init --recursive"
        )


def gather_sources() -> list[str]:
    _require_dir(AIMIO_ROOT / "source", "AimIO")
    sources = [ROOT / "bindings" / "aimio_bindings.cpp"]
    for source in (AIMIO_ROOT / "source").rglob("*"):
        if source.suffix not in {".cxx", ".cpp", ".cc"}:
            continue
        if source.name in SKIP_SOURCE_FILES:
            continue
        sources.append(source)
    return [str(path.relative_to(ROOT)) for path in sources]


def ensure_generated_export_headers() -> str:
    GENERATED_HEADERS_DIR.mkdir(parents=True, exist_ok=True)

    (GENERATED_HEADERS_DIR / "aimio_export.h").write_text(
        """\
#ifndef AIMIO_EXPORT_H
#define AIMIO_EXPORT_H
#define AIMIO_EXPORT
#define AIMIO_NO_EXPORT
#if defined(_MSC_VER)
#define AIMIO_DEPRECATED __declspec(deprecated)
#else
#define AIMIO_DEPRECATED __attribute__((__deprecated__))
#endif
#endif
"""
    )
    (GENERATED_HEADERS_DIR / "n88util_export.h").write_text(
        """\
#ifndef N88UTIL_EXPORT_H
#define N88UTIL_EXPORT_H
#define N88UTIL_EXPORT
#define N88UTIL_NO_EXPORT
#if defined(_MSC_VER)
#define N88UTIL_DEPRECATED __declspec(deprecated)
#else
#define N88UTIL_DEPRECATED __attribute__((__deprecated__))
#endif
#endif
"""
    )
    return str(GENERATED_HEADERS_DIR.relative_to(ROOT))


def gather_include_dirs() -> list[str]:
    _require_dir(AIMIO_ROOT / "include", "AimIO")
    _require_dir(N88UTIL_ROOT / "include", "n88util")

    import numpy
    import pybind11

    generated_headers = ensure_generated_export_headers()
    return [
        generated_headers,
        pybind11.get_include(),
        numpy.get_include(),
        str((AIMIO_ROOT / "include").relative_to(ROOT)),
        str((N88UTIL_ROOT / "include").relative_to(ROOT)),
    ]


ext_modules = [
    Extension(
        "py_aimio._aimio",
        sources=gather_sources(),
        include_dirs=gather_include_dirs(),
        language="c++",
        extra_compile_args=["-std=c++17"] if sys.platform != "win32" else ["/std:c++17"],
    )
]

setup(ext_modules=ext_modules)
