"""
MIT License

Copyright (c) 2016 Eric Nodwell & Steven Boyd

High-level Python API for AimIO bindings.

Provides wrappers around the compiled `_aimio` extension that offer
convenience options like `density=True` on `read_aim` and ensure that
`write_aim` always writes native values.
"""
from pathlib import Path
from typing import Tuple
from importlib.metadata import PackageNotFoundError, version

import numpy as np

try:
    from . import _aimio  # compiled extension
except Exception:
    _aimio = None


from .calibration import (
    decode_scanco_double,
    get_aim_density_equation,
    get_aim_hu_equation,
    get_isq_density_equation,
    get_isq_hu_equation,
)
from .header_log import log_to_dict, dict_to_log
from .gobj import gobj_info, read_gobj
from .scv import read_scv, scv_info


IDENTITY_DIRECTION_3D = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _not_built():
    raise RuntimeError(
        "AimIO extension not built. Ensure submodules are initialized "
        "(`git submodule update --init --recursive`) and run `pip install -e .`."
    )


def _strip_null_padded_ascii(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("ascii", errors="ignore").strip()


def _read_isq_calibration_metadata(path: str, data_offset: int) -> dict:
    if data_offset <= 512:
        return {}

    with open(path, "rb") as handle:
        header = handle.read(data_offset)

    calibration_title = b"Calibration"
    title_at = header.find(calibration_title, 512)
    if title_at < 0:
        return {}

    calibration_start = title_at - 8
    if calibration_start < 0 or calibration_start + 1208 > len(header):
        return {}

    try:
        return {
            "rescale_type": int.from_bytes(header[calibration_start + 1148 : calibration_start + 1152], "little"),
            "rescale_units": _strip_null_padded_ascii(header[calibration_start + 1160 : calibration_start + 1176]),
            "rescale_slope": decode_scanco_double(header[calibration_start + 1176 : calibration_start + 1184]),
            "rescale_intercept": decode_scanco_double(header[calibration_start + 1184 : calibration_start + 1192]),
            "mu_water": decode_scanco_double(header[calibration_start + 1200 : calibration_start + 1208]),
        }
    except Exception:
        return {}


def _augment_isq_meta(path: str, meta: dict) -> dict:
    meta = dict(meta)
    data_offset = int(meta.get("data_offset", 0) or 0)
    meta.update(_read_isq_calibration_metadata(path, data_offset))
    meta = _augment_sitk_geometry_meta(meta)
    return meta


def _augment_sitk_geometry_meta(meta: dict) -> dict:
    meta = dict(meta)
    if "spacing" not in meta and "element_size" in meta:
        meta["spacing"] = tuple(meta["element_size"])
    if "origin" not in meta:
        position = meta.get("position")
        spacing = meta.get("spacing")
        if isinstance(position, (list, tuple)) and len(position) == 3 and isinstance(spacing, (list, tuple)) and len(spacing) == 3:
            offset = meta.get("offset", (0.0, 0.0, 0.0))
            if not (isinstance(offset, (list, tuple)) and len(offset) == 3):
                offset = (0.0, 0.0, 0.0)
            meta["origin"] = tuple(
                (float(position[i]) + float(offset[i])) * float(spacing[i])
                for i in range(3)
            )
            meta["vtkbone_origin"] = tuple(
                (float(position[i]) + float(offset[i]) + 0.5) * float(spacing[i])
                for i in range(3)
            )
        else:
            meta["origin"] = (0.0, 0.0, 0.0)
    if "direction" not in meta:
        meta["direction"] = IDENTITY_DIRECTION_3D
    return meta


def aim_info(path: str):
    """Read AIM header metadata without loading full image data.

    Example:
        >>> meta = aim_info("scan.AIM")
        >>> tuple(meta["dimensions"])
        (256, 256, 200)
    """
    if _aimio is None:
        _not_built()
    return _augment_sitk_geometry_meta(_aimio.aim_info(path))


def isq_info(path: str):
    """Read ISQ header metadata without loading full image data.

    Example:
        >>> meta = isq_info("scan.ISQ")
        >>> tuple(meta["dimensions"])
        (2304, 2304, 168)
    """
    if _aimio is None:
        _not_built()
    meta = _aimio.isq_info(path)
    return _augment_isq_meta(path, meta)


def read_aim(path: str, density: bool = False, hu: bool = False) -> Tuple[np.ndarray, dict]:
    """Read an AIM file and optionally convert to density or HU units.

    Parameters:
        path: AIM file path
        density: if True, convert native values to density using processing log
        hu: if True, convert native values to Hounsfield Units

    Returns:
        (array, meta) where array is a numpy ndarray (possibly float) and meta is the AIM header dict.

    Example:
        >>> arr, meta = read_aim("scan.AIM")
        >>> arr.shape
        (200, 256, 256)
    """
    if _aimio is None:
        _not_built()
    if density and hu:
        raise ValueError("Use only one conversion option: density=True or hu=True")

    arr, meta = _aimio.read_aim(path)
    meta = _augment_sitk_geometry_meta(meta)

    # Keep an unmodified string copy for numeric conversions.
    proc_log_raw = meta.get("processing_log", "")

    # Convert processing_log to a dict for convenient in-Python editing.
    if isinstance(proc_log_raw, str) and proc_log_raw:
        try:
            meta["processing_log"] = log_to_dict(proc_log_raw)
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
        meta["processing_log_raw"] = dict_to_log(meta["processing_log"])

    return arr, meta


def read_isq(path: str, unit: str = "native") -> Tuple[np.ndarray, dict]:
    """Read an ISQ file and optionally convert native values to HU or BMD.

    Parameters:
        path: ISQ file path
        unit: one of ``"native"``, ``"hu"``, ``"density"``, or ``"bmd"``

    Returns:
        (array, meta) where array is a numpy ndarray with shape (z, y, x)
        and meta is the ISQ header dict.
    """
    if _aimio is None:
        _not_built()

    unit_normalized = unit.lower()
    if unit_normalized not in {"native", "hu", "density", "bmd"}:
        raise ValueError("unit must be one of: 'native', 'hu', 'density', or 'bmd'")

    arr, meta = _aimio.read_isq(path)
    meta = _augment_isq_meta(path, meta)

    if unit_normalized == "native":
        meta["unit"] = "native"
        return arr, meta

    if unit_normalized == "hu":
        m, b = get_isq_hu_equation(meta)
        arr = arr.astype(float) * m + b
        meta["unit"] = "HU"
        return arr, meta

    m, b = get_isq_density_equation(meta)
    arr = arr.astype(float) * m + b
    meta["unit"] = "BMD"
    return arr, meta


def _resolve_image_format(path: str, file_format: str = "auto") -> str:
    format_normalized = file_format.lower()
    if format_normalized not in {"auto", "aim", "isq", "scv", "gobj"}:
        raise ValueError("format must be one of: 'auto', 'aim', 'isq', 'scv', or 'gobj'")
    if format_normalized != "auto":
        return format_normalized

    path_without_version = str(path).rsplit(";", 1)[0] if str(path).rsplit(";", 1)[-1].isdigit() else str(path)
    suffix = Path(path_without_version).suffix.lower()
    if suffix == ".aim":
        return "aim"
    if suffix == ".isq":
        return "isq"
    if suffix == ".scv":
        return "scv"
    if suffix == ".gobj":
        return "gobj"
    raise ValueError("Could not infer image format from extension; pass format='aim', 'isq', 'scv', or 'gobj'")


def read_image(path: str, format: str = "auto", **kwargs) -> Tuple[np.ndarray, dict]:
    """Read an AIM, ISQ, SCV, or GOBJ image into a NumPy array plus metadata.

    Parameters:
        path: image file path
        format: ``"auto"``, ``"aim"``, ``"isq"``, ``"scv"``, or ``"gobj"``
        **kwargs: forwarded to the selected reader, e.g. ``unit="hu"`` for ISQ
            or ``density=True`` for AIM.

    Returns:
        (array, meta) from the format-specific reader.
    """
    image_format = _resolve_image_format(str(path), format)
    if image_format == "aim":
        return read_aim(str(path), **kwargs)
    if image_format == "isq":
        return read_isq(str(path), **kwargs)
    if image_format == "scv":
        return read_scv(str(path), **kwargs)
    return read_gobj(str(path), **kwargs)


ReadImage = read_image


def image_info(path: str, format: str = "auto") -> dict:
    """Read AIM, ISQ, SCV, or GOBJ metadata without loading image data.

    Parameters:
        path: image file path
        format: ``"auto"``, ``"aim"``, ``"isq"``, ``"scv"``, or ``"gobj"``

    Returns:
        Metadata dictionary from the format-specific ``*_info`` function.
    """
    image_format = _resolve_image_format(str(path), format)
    if image_format == "aim":
        return aim_info(str(path))
    if image_format == "isq":
        return isq_info(str(path))
    if image_format == "scv":
        return scv_info(str(path))
    return gobj_info(str(path))


ImageInfo = image_info


def write_aim(path: str, array, meta: dict = None, unit: str = None):
    """Write an AIM file. Input is converted back to native units before writing.

    Parameters:
        path: output AIM path
        array: numpy array to write (z,y,x)
        meta: metadata dict; if provided and contains 'processing_log' it will be used for conversions
        unit: optional override of the unit of `array` (e.g., 'HU', 'BMD', 'native')

    Returns:
        header dict from the underlying write call.

    Throws: 
        ValueError if calibration constants incomplete in processing log

    Example:
        >>> arr, meta = read_aim("scan.AIM")
        >>> write_aim("scan_copy.AIM", arr, meta)
    """
    if _aimio is None:
        _not_built()

    if meta is None:
        meta = {}

    proc_log = meta.get("processing_log", "")
    # If processing_log is a dict (editable), convert to string for conversions
    if isinstance(proc_log, dict):
        proc_log_str = dict_to_log(proc_log)
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
        meta_out["processing_log"] = dict_to_log(meta_out["processing_log"])

    return _aimio.write_aim(path, arr_native, meta_out)





__all__ = [
    "aim_info",
    "gobj_info",
    "image_info",
    "isq_info",
    "read_aim",
    "read_gobj",
    "read_image",
    "read_isq",
    "read_scv",
    "ReadImage",
    "ImageInfo",
    "scv_info",
    "write_aim",
    "log_to_dict",
    "dict_to_log",
    "get_aim_density_equation",
    "get_aim_hu_equation",
    "get_isq_density_equation",
    "get_isq_hu_equation",
]

try:
    __version__ = version("aimio-py")
except PackageNotFoundError:
    __version__ = "0.0.0"
