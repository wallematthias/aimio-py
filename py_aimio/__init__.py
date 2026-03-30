"""
MIT License

Copyright (c) 2016 Eric Nodwell & Steven Boyd

High-level Python API for AimIO bindings.

Provides wrappers around the compiled `_aimio` extension that offer
convenience options like `density=True` on `read_aim` and ensure that
`write_aim` always writes native values.
"""
from typing import Tuple
from importlib.metadata import PackageNotFoundError, version

import numpy as np

try:
    from . import _aimio  # compiled extension
except Exception:
    _aimio = None

from .calibration import (
    get_aim_density_equation, get_aim_hu_equation,
)
from .header_log import logtodict, dicttolog


def _not_built():
    raise RuntimeError("AimIO extension not built. Run `pip install -e .` after adding AimIO submodule.")


def aim_info(path: str):
    if _aimio is None:
        _not_built()
    return _aimio.aim_info(path)


def read_aim(path: str, density: bool = False, hu: bool = False) -> Tuple[np.ndarray, dict]:
    """Read an AIM file and optionally convert to density or HU units.

    Parameters:
        path: AIM file path
        density: if True, convert native values to density using processing log
        hu: if True, convert native values to Hounsfield Units

    Returns:
        (array, meta) where array is a numpy ndarray (possibly float) and meta is the AIM header dict.
    """
    if _aimio is None:
        _not_built()
    if density and hu:
        raise ValueError("Use only one conversion option: density=True or hu=True")

    arr, meta = _aimio.read_aim(path)

    # Keep an unmodified string copy for numeric conversions.
    proc_log_raw = meta.get("processing_log", "")

    # Convert processing_log to a dict for convenient in-Python editing.
    if isinstance(proc_log_raw, str) and proc_log_raw:
        try:
            meta["processing_log"] = logtodict(proc_log_raw)
        except Exception:
            # leave as string if parsing fails
            pass

    if density:
        m, b = get_aim_density_equation(proc_log_raw)
        arr = arr.astype(float) * m + b
        meta["unit"] = "BMD"
    elif hu:
        m, b = get_aim_hu_equation(proc_log_raw)
        arr = arr.astype(float) * m + b
        meta["unit"] = "HU"

    # Keep a string copy available for any downstream conversion/write operation.
    if isinstance(meta.get("processing_log"), str):
        meta["processing_log_raw"] = meta["processing_log"]
    elif isinstance(meta.get("processing_log"), dict):
        meta["processing_log_raw"] = dicttolog(meta["processing_log"])

    return arr, meta


def write_aim(path: str, array, meta: dict = None, unit: str = None):
    """Write an AIM file. Input is converted back to native units before writing.

    Parameters:
        path: output AIM path
        array: numpy array to write (z,y,x)
        meta: metadata dict; if provided and contains 'processing_log' it will be used for conversions
        unit: optional override of the unit of `array` (e.g., 'HU', 'BMD', 'native')

    Returns:
        header dict from the underlying write call.
    """
    if _aimio is None:
        _not_built()

    if meta is None:
        meta = {}

    proc_log = meta.get("processing_log", "")
    # If processing_log is a dict (editable), convert to string for conversions
    if isinstance(proc_log, dict):
        proc_log_str = dicttolog(proc_log)
    else:
        proc_log_str = meta.get("processing_log_raw", proc_log)
    cur_unit = (unit or meta.get("unit", "native"))

    arr = np.asarray(array)

    # If array is not in native units, convert back: Native = (value - b) / m
    if cur_unit in ("BMD", "density"):
        m, b = get_aim_density_equation(proc_log_str)
        arr_native = (arr.astype(float) - b) / m
    elif cur_unit == "HU":
        m, b = get_aim_hu_equation(proc_log_str)
        arr_native = (arr.astype(float) - b) / m
    else:
        arr_native = arr

    # Ensure we pass a contiguous array with z,y,x ordering
    arr_native = np.ascontiguousarray(arr_native)

    # Ensure processing_log is a string when passing to the low-level writer
    meta_out = dict(meta)
    if isinstance(meta_out.get("processing_log"), dict):
        meta_out["processing_log"] = dicttolog(meta_out["processing_log"])

    return _aimio.write_aim(path, arr_native, meta_out)


def aim_to_sitk(file_path, scaling, write_mha=False):
    """Lazy wrapper to avoid importing optional heavy deps at package import time."""
    from .converters import aim_to_sitk as _aim_to_sitk

    return _aim_to_sitk(file_path=file_path, scaling=scaling, write_mha=write_mha)


def sitk_to_aim(file_path="", sitk_img=None, write_aim=False, output_path=""):
    """Lazy wrapper to avoid importing optional heavy deps at package import time."""
    from .converters import sitk_to_aim as _sitk_to_aim

    return _sitk_to_aim(
        file_path=file_path,
        sitk_img=sitk_img,
        write_aim=write_aim,
        output_path=output_path,
    )


__all__ = [
    "aim_info",
    "read_aim",
    "write_aim",
    "aim_to_sitk",
    "sitk_to_aim",
    "logtodict",
    "dicttolog",
    "get_aim_density_equation",
    "get_aim_hu_equation",
]

try:
    __version__ = version("py-aimio")
except PackageNotFoundError:
    __version__ = "0.0.0"
