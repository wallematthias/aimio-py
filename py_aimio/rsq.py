"""Storage reader for the supported CTDATA-HEADER_V1 RSQ interpretation.

RSQ arrays contain raw detector counts in (detector row, frame, detector
column) order. They are projections rather than reconstructed spatial volumes.
The unsigned interpretation and geometry hints are not a guarantee for every
proprietary Scanco RSQ variant.
"""

from __future__ import annotations

from math import prod
import os
from pathlib import Path
import re
import struct
from typing import BinaryIO

import numpy as np


_BLOCK_SIZE = 512
_MAGIC = b"CTDATA-HEADER_V1"
_DTYPE = np.dtype("<u2")
_FLOAT = rb"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_ANCHORS = re.compile(rb"Corr at 2 3 6:\s*(" + _FLOAT + rb")\s+(" + _FLOAT + rb")\s+(" + _FLOAT + rb")")


def _beam_hardening(block: bytes) -> dict:
    if b"Beamhard.Corr." not in block[:24]:
        return {
            "available": False,
            "reason": "No recognized Beamhard.Corr. calibration in the final header block",
        }

    coefficients = struct.unpack_from("<3d", block, 476)
    match = _ANCHORS.search(block[:476])
    if match is None:
        raise ValueError("RSQ beam-hardening calibration is missing valid Corr at 2 3 6 anchors")
    anchors = tuple(float(value) for value in match.groups())
    if not all(np.isfinite(value) for value in coefficients + anchors):
        raise ValueError("RSQ beam-hardening calibration contains non-finite values")

    a1, a2, a3 = coefficients
    p = np.array([2.0, 3.0, 6.0])
    with np.errstate(over="ignore", invalid="ignore"):
        predicted = a1 * p + a2 * p**2 + a3 * p**3
    if not np.allclose(predicted, anchors, atol=1e-6, rtol=0):
        raise ValueError("RSQ beam-hardening calibration coefficients do not match printed anchors")
    return {
        "available": True,
        "coefficients": coefficients,
        "anchors": anchors,
        "anchor_positions": (2.0, 3.0, 6.0),
        "polynomial": "delta(p) = a1*p + a2*p**2 + a3*p**3",
        "provenance": "Final 512-byte header block: <3d at bytes 476:500, checked against printed anchors",
    }


def _geometry(words: tuple[int, ...]) -> dict:
    object_views = words[65]
    return {
        "requested_spacing_um": (words[17], words[18]),
        "axial_start_um": words[19],
        "native_horizontal_samples": words[23],
        "active_native_rows": words[24],
        "detector_width_um": words[25],
        "detector_height_um": words[26],
        "source_detector_distance_um": words[29],
        "source_axis_distance_um": words[30],
        "binning": words[49],
        "object_view_count": object_views,
        "angular_interval_mdeg": words[15],
        "angular_step_mdeg": words[15] / object_views if object_views else None,
        "provenance": (
            "Partially inferred CTDATA header interpretation; units and meanings are "
            "supported hints, not independently validated reconstruction geometry"
        ),
        "header_word_indices": {
            "requested_spacing_um": (17, 18), "axial_start_um": 19,
            "native_horizontal_samples": 23, "active_native_rows": 24,
            "detector_width_um": 25, "detector_height_um": 26,
            "source_detector_distance_um": 29, "source_axis_distance_um": 30,
            "binning": 49, "object_view_count": 65, "angular_interval_mdeg": 15,
        },
    }


def _read_metadata(handle: BinaryIO, path: str | Path) -> dict:
    header = handle.read(_BLOCK_SIZE)
    if len(header) != _BLOCK_SIZE:
        raise ValueError("RSQ file is truncated: a complete 512-byte base header is required")
    if header[:16] != _MAGIC:
        raise ValueError("Unsupported RSQ magic: expected CTDATA-HEADER_V1")

    words = struct.unpack("<128I", header)
    shape = (words[13], words[12], words[11])
    if any(dimension == 0 for dimension in shape):
        raise ValueError("RSQ dimensions must all be positive")
    data_offset = _BLOCK_SIZE * (words[127] + 1)
    file_size = os.fstat(handle.fileno()).st_size
    if data_offset > file_size:
        raise ValueError("RSQ data offset extends beyond the file header and payload")
    payload_size = _DTYPE.itemsize * prod(shape)
    expected_size = data_offset + payload_size
    padding_size = file_size - expected_size
    if padding_size and not (0 < padding_size == (-expected_size) % _BLOCK_SIZE):
        raise ValueError(
            f"RSQ payload size mismatch: expected {payload_size} bytes for shape {shape}, "
            f"found {file_size - data_offset}"
        )
    if padding_size:
        handle.seek(expected_size)
        padding = handle.read(padding_size)
        if len(padding) != padding_size or any(padding):
            raise ValueError("RSQ block padding must contain only zero bytes")

    if words[127]:
        handle.seek(words[127] * _BLOCK_SIZE)
        final_block = handle.read(_BLOCK_SIZE)
        if len(final_block) != _BLOCK_SIZE:
            raise ValueError("RSQ final calibration header block is truncated")
    else:
        final_block = header

    return {
        "format": "RSQ",
        "filename": str(path),
        "magic": _MAGIC.decode("ascii"),
        "header_words": words,
        "shape": shape,
        "dimensions": shape,
        "axis_order": ("detector_row", "frame", "detector_column"),
        "dtype": _DTYPE.str,
        "dtype_interpretation": (
            "Supported interpretation: little-endian unsigned 16-bit detector counts; "
            "signedness has not been independently confirmed for all RSQ variants"
        ),
        "data_offset_bytes": data_offset,
        "payload_size_bytes": payload_size,
        "padding_size_bytes": padding_size,
        "unit": "detector_counts",
        "count_range": (words[21], words[22]),
        "frame_interpretation": (
            "Stored frames may include reference frames as well as object views; "
            "the storage reader does not classify or discard frames"
        ),
        "geometry": _geometry(words),
        "beam_hardening": _beam_hardening(final_block),
    }


def rsq_info(path: str | Path) -> dict:
    """Read RSQ metadata and validate storage without reading detector payload.

    Only headers and optional final-block padding are read, not detector counts.
    File size must match the declared shape and offset, optionally followed by
    zero bytes up to the next 512-byte boundary. ``header_words`` contains all
    128 little-endian unsigned words; patient-name fields are not decoded.
    Interpreted geometry is exposed with provenance and is not spatial image
    geometry. Recognized but corrupt beam-hardening calibration raises
    ``ValueError``; absent or unrecognized calibration is marked unavailable.
    """
    with open(path, "rb") as handle:
        return _read_metadata(handle, path)


def read_rsq(path: str | Path, *, mmap: bool = False) -> tuple[np.ndarray, dict]:
    """Read supported RSQ raw detector counts in (row, frame, column) order.

    Parameters:
        path: RSQ file path, including a VMS version suffix when present.
        mmap: Return a read-only NumPy memmap instead of loading the payload.

    Returns:
        ``(counts, meta)`` with a little-endian unsigned 16-bit array. Every
        stored frame is retained, including any reference frames. No minimum
        reconstruction view count, calibration application, spatial conversion,
        density conversion, or HU conversion is performed.

    Raises:
        ValueError: Unsupported magic, invalid dimensions or payload length,
            or corrupt recognized beam-hardening calibration.
    """
    with open(path, "rb") as handle:
        meta = _read_metadata(handle, path)
        if mmap:
            counts = np.memmap(
                handle, dtype=_DTYPE, mode="r", offset=meta["data_offset_bytes"],
                shape=meta["shape"], order="C",
            )
        else:
            handle.seek(meta["data_offset_bytes"])
            counts = np.fromfile(handle, dtype=_DTYPE, count=prod(meta["shape"]))
            if counts.size != prod(meta["shape"]):
                raise ValueError("RSQ payload was truncated while reading detector counts")
            counts = counts.reshape(meta["shape"])
    return counts, meta
