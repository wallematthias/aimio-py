import struct
from pathlib import Path

import numpy as np
import pytest

import py_aimio as api


def _vms_float(value):
    raw = struct.pack("<f", value * 4.0)
    return raw[2:4] + raw[0:2]


def _encode_profile(values):
    encoded = bytearray()
    index = 0
    while index < len(values):
        value = values[index]
        repeat_count = 1
        while index + repeat_count < len(values) and values[index + repeat_count] == value and repeat_count < 6:
            index += 1
            repeat_count += 1
        if repeat_count >= 2:
            encoded.extend([256 - repeat_count, value])
        else:
            encoded.append(value)
        index += 1
    return bytes(encoded)


def _write_scv(path):
    header = bytearray(107)
    header[0:2] = b"\x03\x00"
    header[2:42] = b"PEDFX_014".ljust(40, b" ")
    header[66:70] = struct.pack("<i", 8)
    header[70:74] = struct.pack("<i", 6)
    header[74:78] = _vms_float(8.0)
    header[78:82] = _vms_float(6.0)
    header[83:87] = _vms_float(1.5)
    header[95:99] = _vms_float(0.0)
    header[99:103] = _vms_float(0.5)
    header[103:107] = struct.pack("<i", 1)

    profiles = [
        (256, [1, 2, 2, 2, 3, 3]),
        (254, [4, 4, 5, 6, 6, 6]),
        (252, [7, 8, 8, 9, 9, 9]),
    ]
    payload = bytearray(header)
    for column, (aux, profile) in enumerate(profiles):
        encoded = _encode_profile(profile)
        byte_count = len(encoded) + 2
        payload += struct.pack("<f", (100.0 + column) * 4.0)
        payload += struct.pack("<HHH", column, byte_count, aux)
        payload += encoded
    path.write_bytes(payload)
    return profiles


def test_scv_info_reads_scout_metadata(tmp_path):
    path = tmp_path / "tiny.SCV"
    profiles = _write_scv(path)

    info = api.scv_info(path)

    assert info["format"] == "SCV"
    assert info["magic"] == "PEDFX_014"
    assert info["identifier"] == "PEDFX_014"
    assert info["header_dimensions"] == (6, 8)
    assert info["dimensions"] == (6, 8)
    assert info["dim_x_mm"] == 8.0
    assert info["dim_y_mm"] == 6.0
    assert info["spacing"] == (1.0, 1.0, 1.0)
    assert info["origin"] == (0.0, 100.0, 0.0)
    assert info["direction"] == api.IDENTITY_DIRECTION_3D
    assert info["record_start"] == 107
    assert info["record_count"] == 3
    assert info["dim_x_pixel"] == 8
    assert info["dim_y_pixel"] == 6
    assert len(info["records"]) == 3
    assert info["records"][0]["aux"] == profiles[0][0]
    assert info["records"][0]["decoded_size"] == len(profiles[0][1])


def test_read_scv_is_pure_python_and_reconstructs_rows(tmp_path, monkeypatch):
    path = tmp_path / "tiny.SCV"
    profiles = _write_scv(path)
    monkeypatch.setattr(api, "_aimio", None)

    image, info = api.read_scv(path)

    assert info["dimensions"] == (6, 8)
    assert image.dtype == np.uint8
    assert image.shape == (6, 8)
    expected = np.zeros((6, 8), dtype=np.uint8)
    for row, (aux, profile) in enumerate(profiles):
        left = 256 - aux
        expected[row, left : left + len(profile)] = profile[: 8 - left]
    assert np.array_equal(image, expected)


def test_scv_rejects_unsupported_magic(tmp_path):
    path = tmp_path / "not_scv.SCV"
    path.write_bytes(b"\x03\x00NOT_SCV".ljust(107, b"\0"))

    with pytest.raises(ValueError, match="Unsupported SCV header"):
        api.scv_info(path)


def test_scv_matches_reference_aim_when_local_pair_is_available():
    folder = Path("/Users/matthias.walle/Downloads/scv_example 2")
    scv_path = folder / "00000039020.SCV"
    aim_path = folder / "0000003920_SCV.AIM"
    if not scv_path.exists() or not aim_path.exists():
        pytest.skip("local paired SCV/AIM regression data is not available")

    scv_image, scv_meta = api.read_scv(scv_path)
    aim_image, aim_meta = api.read_aim(str(aim_path))

    assert scv_meta["dimensions"] == (372, 512)
    assert tuple(aim_meta["dimensions"]) == (512, 372, 1)
    assert scv_meta["identifier"] == "Normal Volunteer Study; 009 Radius"
    assert scv_meta["spacing"] == pytest.approx(aim_meta["spacing"])
    assert scv_meta["origin"] == pytest.approx(aim_meta["origin"])
    assert scv_meta["direction"] == aim_meta["direction"]
    assert scv_meta["records"][0]["position"] == pytest.approx(90.0, abs=1e-4)
    assert scv_meta["records"][-1]["position"] == pytest.approx(121.7943, abs=1e-4)
    assert np.array_equal(scv_image.astype(np.int16) * 16, aim_image[0])
