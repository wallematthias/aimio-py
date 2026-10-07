"""Read native CTDATA-HEADER_V1, type-9 Scanco scout radiographs.

Header field interpretation follows David Gobbi's vtk-dicom Scanco reader:
https://github.com/dgobbi/vtk-dicom/blob/master/Source/vtkScancoCTReader.cxx
RAD physical dimensions are nanometres, unlike ISQ's micrometres. Scanner
reference positions are metadata, not a reconstructed-volume world transform.
"""

from __future__ import annotations

import os
from pathlib import Path
import struct
from typing import BinaryIO

import numpy as np


_BLOCK_SIZE = 512
_MAGIC = b"CTDATA-HEADER_V1"
_DTYPE = np.dtype("<i2")
_IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def _read_metadata(handle: BinaryIO, path: str | Path) -> dict:
    header = handle.read(_BLOCK_SIZE)
    if len(header) != _BLOCK_SIZE:
        raise ValueError("RAD file is truncated: a complete 512-byte header is required")
    if header[:16] != _MAGIC:
        raise ValueError("Unsupported RAD magic: expected CTDATA-HEADER_V1")
    words = struct.unpack("<128i", header)
    if words[4] != 9:
        raise ValueError("Unsupported RAD data type: expected type 9 native radiograph")
    width, height, depth = words[11:14]
    if width <= 0 or height <= 0 or depth != 1:
        raise ValueError("RAD requires positive width/height and exactly one radiograph plane")
    physical_nm = words[14:17]
    if physical_nm[0] <= 0 or physical_nm[1] <= 0 or physical_nm[2] < 0:
        raise ValueError("RAD physical header extents are invalid")
    if words[127] < 0:
        raise ValueError("RAD extra-header block count must be nonnegative")
    data_offset = _BLOCK_SIZE * (words[127] + 1)
    file_size = os.fstat(handle.fileno()).st_size
    if data_offset > file_size:
        raise ValueError("RAD data offset extends beyond the file")
    payload_size = _DTYPE.itemsize * width * height
    expected_size = data_offset + payload_size
    padding_size = file_size - expected_size
    if padding_size and not (0 < padding_size == (-expected_size) % _BLOCK_SIZE):
        raise ValueError("RAD payload size does not match the declared dimensions")
    if padding_size:
        handle.seek(expected_size)
        padding = handle.read(padding_size)
        if len(padding) != padding_size or any(padding):
            raise ValueError("RAD block padding must contain only zero bytes")

    physical_mm = tuple(value * 1e-6 for value in physical_nm)
    spacing = (physical_mm[0] / width, physical_mm[1] / height, 1.0)
    return {
        "format": "RAD",
        "filename": str(path),
        "magic": _MAGIC.decode("ascii"),
        "data_type": words[4],
        "header_words": words,
        "patient_index": words[7],
        "scanner_id": words[8],
        "measurement_index": words[17],
        "patient_name": header[84:124].split(b"\0", 1)[0].decode("ascii", errors="replace").strip(),
        "dimensions": (width, height, depth),
        "shape": (height, width),
        "axis_order": ("row", "column"),
        "dtype": _DTYPE.str,
        "physical_dimensions_nm": physical_nm,
        "physical_dimensions_mm": physical_mm,
        "spacing": spacing,
        "element_size": spacing,
        "origin": (0.0, 0.0, 0.0),
        "direction": _IDENTITY,
        "geometry_unit": "mm",
        "geometry_source": "rad_header_nanometres",
        "geometry_note": "2D scout plane; identity direction and zero origin are display conventions, not CT co-registration.",
        "data_offset_bytes": data_offset,
        "payload_size_bytes": payload_size,
        "padding_size_bytes": padding_size,
        "unit": "native",
        "data_range": words[18:20],
        "mu_scaling": words[20],
        "z_position_mm": words[31] * 1e-3,
        "sample_time_ms": words[33] * 1e-3,
        "energy_kv": words[34] * 1e-3,
        "intensity_ma": words[35] * 1e-3,
        "reference_line_mm": words[36] * 1e-3,
        "start_position_mm": words[37] * 1e-3,
        "end_position_mm": words[38] * 1e-3,
    }


def rad_info(path: str | Path) -> dict:
    """Inspect a type-9 RAD header and validate payload size without loading pixels.

    Spacing is in mm, dimensions in XYZ order, and shape in row/column order.
    Exact payload length or zero padding to the next 512-byte block is required.
    Unsupported types, corrupt geometry, and truncated storage raise ValueError.
    """
    with open(path, "rb") as handle:
        return _read_metadata(handle, path)


def read_rad(path: str | Path) -> tuple[np.ndarray, dict]:
    """Read a RAD as a 2D signed-int16 array and physically spaced metadata.

    Preserves native values and row order. No HU/density conversion is applied;
    this is a projection radiograph, not a reconstructed CT volume. Header
    scanner positions remain separate from the zero-origin display geometry.
    """
    with open(path, "rb") as handle:
        meta = _read_metadata(handle, path)
        handle.seek(meta["data_offset_bytes"])
        count = meta["shape"][0] * meta["shape"][1]
        pixels = np.fromfile(handle, dtype=_DTYPE, count=count)
        if pixels.size != count:
            raise ValueError("RAD payload was truncated while reading pixels")
        return pixels.reshape(meta["shape"]), meta
