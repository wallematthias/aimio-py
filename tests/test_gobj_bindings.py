import struct

import numpy as np
import pytest

import py_aimio as api


DIR_TO_CODE = {
    (0, 1): 6,
    (1, 0): 0,
    (0, -1): 2,
    (-1, 0): 4,
}


def _pack_3bit(values):
    payload = bytearray()
    accumulator = 0
    bits = 0
    for value in values:
        accumulator |= int(value) << bits
        bits += 3
        while bits >= 8:
            payload.append(accumulator & 0xFF)
            accumulator >>= 8
            bits -= 8
    if bits:
        payload.append(accumulator & 0xFF)
    return bytes(payload)


def _codes_for_rectangle(width, height):
    steps = []
    steps.extend([(0, 1)] * (height - 1))
    steps.extend([(1, 0)] * (width - 1))
    steps.extend([(0, -1)] * (height - 1))
    steps.extend([(-1, 0)] * (width - 1))
    return [DIR_TO_CODE[step] for step in steps]


def _contour_record(material, center_x, center_y, z, width, height, header_size=72):
    codes = _codes_for_rectangle(width, height)
    packed = _pack_3bit(codes)
    if header_size == 72:
        return (
            struct.pack(
                "<18i",
                material,
                3,
                center_x,
                center_y,
                z,
                width,
                height,
                0,
                3,
                32,
                0,
                0,
                16512,
                16512,
                0,
                0,
                len(codes),
                len(packed),
            )
            + packed
        )
    return (
        struct.pack(
            "<17i",
            material,
            center_x,
            center_y,
            z,
            width,
            height,
            0,
            3,
            32,
            0,
            0,
            16512,
            16512,
            0,
            0,
            len(codes),
            len(packed),
        )
        + packed
    )


def _write_gobj(path, include_inner=False):
    center_x = 12
    center_y = 15
    width = 6
    height = 5
    z = 0

    header = bytearray(512)
    header[:16] = b"CTDATA-HEADER_V1"
    header[16:20] = struct.pack("<i", 6)
    header[32:44] = struct.pack("<3i", 32, 32, 1)
    header[44:56] = struct.pack("<3i", 3200, 3200, 100)
    header[508:512] = struct.pack("<i", 0)

    top = struct.pack(
        "<13i",
        1,
        center_x,
        center_y,
        z,
        width,
        height,
        0,
        3,
        20,
        0,
        0,
        16512,
        16512,
    )
    outer = _contour_record(1, center_x, center_y, z, width, height, header_size=72)
    inner = b""
    if include_inner:
        inner = _contour_record(3, center_x, center_y, z, 4, 3, header_size=68)
    path.write_bytes(bytes(header) + top + outer + inner)


def _write_primitive_gobj(path):
    header = bytearray(512)
    header[:16] = b"CTDATA-HEADER_V1"
    header[16:20] = struct.pack("<i", 6)
    header[32:44] = struct.pack("<3i", 16, 16, 1)
    header[44:56] = struct.pack("<3i", 1600, 1600, 100)
    header[508:512] = struct.pack("<i", 0)

    center_x = 6
    center_y = 7
    z = 0
    width = 8
    height = 8
    top = struct.pack(
        "<13i",
        1,
        center_x,
        center_y,
        z,
        width,
        height,
        0,
        3,
        20,
        0,
        0,
        16512,
        16512,
    )
    parent_rectangle = struct.pack(
        "<10i",
        6,
        4,
        center_x,
        center_y,
        z,
        width,
        height,
        0,
        3,
        0,
    )
    child_circle = struct.pack(
        "<9i",
        6,
        center_x,
        center_y,
        z,
        4,
        4,
        0,
        3,
        0,
    )
    path.write_bytes(bytes(header) + top + parent_rectangle + child_circle)


def test_gobj_info_reads_contour_metadata(tmp_path):
    path = tmp_path / "mask.GOBJ"
    _write_gobj(path)

    info = api.gobj_info(path)

    assert info["format"] == "GOBJ"
    assert info["data_type"] == 6
    assert info["dimensions"] == (6, 5, 1)
    assert info["position"] == (10, 13, 0)
    assert info["spacing"] == (0.1, 0.1, 0.1)
    assert info["direction"] == api.IDENTITY_DIRECTION_3D
    assert info["slice_count"] == 1
    assert info["contour_count"] == 1


def test_read_gobj_reconstructs_binary_mask_without_extension(tmp_path, monkeypatch):
    path = tmp_path / "mask.bin"
    _write_gobj(path)
    monkeypatch.setattr(api, "_aimio", None)

    image, info = api.read_image(path, format="gobj")

    expected = np.full((1, 5, 6), 127, dtype=np.uint8)
    assert image.dtype == np.uint8
    assert np.array_equal(image, expected)
    assert info["unit"] == "native"
    assert info["rasterization"]["crop"] == "tight"
    assert info["rasterization"]["output_value"] == 127
    assert info["rasterization"]["subtractive_contours"] == "strict_interior"


def test_read_gobj_supports_binary_value_and_header_crop(tmp_path):
    path = tmp_path / "mask.GOBJ"
    _write_gobj(path)

    image, info = api.read_gobj(path, value=1, crop="header")

    expected = np.zeros((1, 32, 32), dtype=np.uint8)
    expected[:, 13:18, 10:16] = 1
    assert np.array_equal(image, expected)
    assert info["dimensions"] == (32, 32, 1)
    assert info["position"] == (0, 0, 0)
    assert info["rasterization"]["crop"] == "header"
    assert info["rasterization"]["output_value"] == 1


def test_gobj_primitive_parent_subtracts_child_interior(tmp_path):
    path = tmp_path / "primitive.GOBJ"
    _write_primitive_gobj(path)

    image, info = api.read_gobj(path, value=1)

    assert image.shape == (1, 8, 8)
    assert image.dtype == np.uint8
    assert info["primitive_count"] == 2
    assert info["contour_count"] == 0
    assert info["primitive_shapes"] == [4, 6]
    assert image[0, 0, 0] == 1
    assert image[0, 3, 3] == 0
    assert np.count_nonzero(image) < 64


def test_read_gobj_validates_options(tmp_path):
    path = tmp_path / "mask.GOBJ"
    _write_gobj(path)

    with pytest.raises(ValueError, match="crop must be one of"):
        api.read_gobj(path, crop="banana")

    with pytest.raises(ValueError, match="value must fit"):
        api.read_gobj(path, value=300)


def test_gobj_subtractive_contour_removes_strict_interior(tmp_path):
    path = tmp_path / "ring.GOBJ"
    _write_gobj(path, include_inner=True)

    image, _info = api.read_gobj(path)

    expected = np.full((1, 5, 6), 127, dtype=np.uint8)
    expected[:, 1, 1:5] = 127
    expected[:, 2, 1] = 127
    expected[:, 2, 2:4] = 0
    expected[:, 2, 4] = 127
    expected[:, 3, 1:5] = 127
    assert np.array_equal(image, expected)
