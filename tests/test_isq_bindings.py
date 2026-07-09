from __future__ import annotations

import math
import struct
from pathlib import Path

import numpy as np

import py_aimio as api


def _write_tiny_isq(path: Path, data: np.ndarray) -> None:
    nz, ny, nx = data.shape
    flat = np.asarray(data, dtype="<i2").reshape(-1)
    header = bytearray(512)

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
        88: 4096,
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
        508: 0,
    }
    for offset, value in values.items():
        struct.pack_into("<i", header, offset, value)

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
