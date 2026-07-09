from __future__ import annotations

import math
import struct
from pathlib import Path

import numpy as np
import pytest

import py_aimio as api


def _encode_scanco_double(value: float) -> bytes:
    bits = struct.unpack("<Q", struct.pack("<d", value / 0.25))[0]
    high = (bits >> 32) & 0xFFFFFFFF
    low = bits & 0xFFFFFFFF
    return bytes(
        [
            (high >> 16) & 0xFF,
            (high >> 24) & 0xFF,
            high & 0xFF,
            (high >> 8) & 0xFF,
            (low >> 16) & 0xFF,
            (low >> 24) & 0xFF,
            low & 0xFF,
            (low >> 8) & 0xFF,
        ]
    )


def _write_tiny_isq(
    path: Path,
    data: np.ndarray,
    *,
    extended_calibration: bool = False,
    mu_scaling: int = 4096,
    rescale_slope: float = 2.0,
    rescale_intercept: float = 3.0,
    mu_water: float = 1.0,
) -> None:
    nz, ny, nx = data.shape
    flat = np.asarray(data, dtype="<i2").reshape(-1)
    header_size = 2560 if extended_calibration else 512
    header = bytearray(header_size)

    header[:16] = b"CTDATA-HEADER_V1"
    nr_of_bytes = len(header) + flat.nbytes
    values = {
        16: 3,
        20: nr_of_bytes,
        24: math.ceil(nr_of_bytes / 512),
        28: 1234,
        32: 3505,
        44: nx,
        48: ny,
        52: nz,
        56: nx * 100,
        60: ny * 200,
        64: nz * 500,
        68: 500,
        72: 500,
        76: 42,
        80: int(flat.min()),
        84: int(flat.max()),
        88: mu_scaling,
        92: nx,
        96: 900,
        100: 300,
        104: 9,
        108: 43000,
        112: 5678,
        116: 4,
        120: 42,
        124: 3,
        168: 68000,
        172: 1470,
        508: 4 if extended_calibration else 0,
    }
    for offset, value in values.items():
        struct.pack_into("<i", header, offset, value)

    if extended_calibration:
        header[512 + 8 : 512 + 24] = b"MultiHeader     "
        struct.pack_into("<i", header, 512 + 24, 1)
        cal = 1024
        header[cal + 8 : cal + 24] = b"Calibration     "
        struct.pack_into("<i", header, cal + 24, 2)
        struct.pack_into("<i", header, cal + 1148, 1)
        header[cal + 1160 : cal + 1176] = b"mg HA/ccm".ljust(16, b"\0")
        header[cal + 1176 : cal + 1184] = _encode_scanco_double(rescale_slope)
        header[cal + 1184 : cal + 1192] = _encode_scanco_double(rescale_intercept)
        header[cal + 1200 : cal + 1208] = _encode_scanco_double(mu_water)

    path.write_bytes(bytes(header) + flat.tobytes())


def test_isq_info_and_read_isq_use_scanco_reader(tmp_path):
    data = np.arange(12, dtype=np.int16).reshape(2, 2, 3)
    path = tmp_path / "tiny.ISQ"
    _write_tiny_isq(path, data)

    info = api.isq_info(str(path))
    arr, meta = api.read_isq(str(path))

    assert info["dimensions"] == (3, 2, 2)
    assert info["dimensions_um"] == (300, 400, 1000)
    assert info["spacing"] == (100.0, 200.0, 500.0)
    assert info["mu_scaling"] == 4096
    assert meta["data_type"] == 3
    assert arr.shape == (2, 2, 3)
    assert arr.dtype == np.int16
    assert np.array_equal(arr, data)


def test_read_isq_hu_conversion_uses_extended_calibration(tmp_path):
    data = np.array([[[0, 1]]], dtype=np.int16)
    path = tmp_path / "calibrated.ISQ"
    _write_tiny_isq(path, data, extended_calibration=True, mu_scaling=1000, mu_water=1.0)

    arr, meta = api.read_isq(str(path), unit="hu")

    assert np.allclose(arr, np.array([[[-1000.0, -999.0]]]))
    assert meta["unit"] == "HU"
    assert meta["rescale_slope"] == 2.0
    assert meta["rescale_intercept"] == 3.0
    assert meta["mu_water"] == 1.0


def test_read_isq_density_and_bmd_conversion_use_extended_calibration(tmp_path):
    data = np.array([[[0, 1]]], dtype=np.int16)
    path = tmp_path / "calibrated.ISQ"
    _write_tiny_isq(path, data, extended_calibration=True, rescale_slope=2.0, rescale_intercept=3.0)

    density_arr, density_meta = api.read_isq(str(path), unit="density")
    bmd_arr, bmd_meta = api.read_isq(str(path), unit="bmd")

    assert np.allclose(density_arr, np.array([[[3.0, 5.0]]]))
    assert np.allclose(bmd_arr, density_arr)
    assert density_meta["unit"] == "BMD"
    assert bmd_meta["unit"] == "BMD"


def test_read_isq_default_and_native_units_are_unchanged(tmp_path):
    data = np.array([[[0, 1]]], dtype=np.int16)
    path = tmp_path / "calibrated.ISQ"
    _write_tiny_isq(path, data, extended_calibration=True)

    default_arr, default_meta = api.read_isq(str(path))
    native_arr, native_meta = api.read_isq(str(path), unit="native")

    assert np.array_equal(default_arr, data)
    assert np.array_equal(native_arr, data)
    assert default_arr.dtype == np.int16
    assert native_meta["unit"] == "native"
    assert default_meta["unit"] == "native"


def test_read_isq_requires_supported_unit(tmp_path):
    data = np.array([[[0, 1]]], dtype=np.int16)
    path = tmp_path / "tiny.ISQ"
    _write_tiny_isq(path, data)

    with pytest.raises(ValueError, match="unit must be one of"):
        api.read_isq(str(path), unit="banana")


def test_read_isq_requires_calibration_for_density(tmp_path):
    data = np.array([[[0, 1]]], dtype=np.int16)
    path = tmp_path / "tiny.ISQ"
    _write_tiny_isq(path, data)

    with pytest.raises(ValueError, match="ISQ calibration metadata"):
        api.read_isq(str(path), unit="density")
