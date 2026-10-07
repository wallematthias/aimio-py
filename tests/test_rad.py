"""Independent CTDATA fixtures: RAD lengths are nanometres, not ISQ micrometres."""

import json
import struct

import numpy as np
import pytest

import py_aimio as api
from py_aimio import cli


def _write_rad(path, *, extra_blocks=0, padded=False):
    header = bytearray(512 * (extra_blocks + 1))
    header[:16] = b"CTDATA-HEADER_V1"
    struct.pack_into("<i", header, 16, 9)
    struct.pack_into("<ii", header, 28, 12, 3514)
    struct.pack_into("<3i", header, 44, 4, 2, 1)
    struct.pack_into("<3i", header, 56, 240000, 160000, 0)
    struct.pack_into("<4i", header, 68, 34, -32768, 32767, 4096)
    header[84:124] = b"Synthetic scout".ljust(40, b" ")
    struct.pack_into("<i", header, 124, 140000)
    struct.pack_into("<6i", header, 132, 43, 68000, 1470, 164762, 173762, 183959)
    struct.pack_into("<i", header, 508, extra_blocks)
    if extra_blocks:
        header[512:] = b"X" * (len(header) - 512)
    pixels = struct.pack("<8h", -32768, -1, 0, 1, 256, 4096, 9186, 32767)
    data = bytes(header) + pixels
    if padded:
        data += b"\0" * (-len(data) % 512)
    path.write_bytes(data)
    return data


@pytest.mark.parametrize("extra_blocks,padded", [(0, False), (1, False), (0, True)])
def test_rad_preserves_signed_pixels_and_converts_nanometres_to_mm(tmp_path, monkeypatch, extra_blocks, padded):
    path = tmp_path / "scout.RAD"
    original = _write_rad(path, extra_blocks=extra_blocks, padded=padded)
    monkeypatch.setattr(api, "_aimio", None)

    image, meta = api.read_rad(path)

    assert image.dtype == np.dtype("<i2")
    assert image.tolist() == [[-32768, -1, 0, 1], [256, 4096, 9186, 32767]]
    assert meta["dimensions"] == (4, 2, 1)
    assert meta["shape"] == (2, 4)
    assert meta["spacing"] == pytest.approx((0.06, 0.08, 1.0))
    assert meta["physical_dimensions_mm"] == pytest.approx((0.24, 0.16, 0.0))
    assert meta["origin"] == (0.0, 0.0, 0.0)
    assert meta["unit"] == "native"
    assert meta["geometry_unit"] == "mm"
    assert meta["z_position_mm"] == 140.0  # Scanner coordinates do not place a CT volume.
    assert meta["reference_line_mm"] == 164.762
    assert meta["patient_index"] == 12
    assert meta["measurement_index"] == 34
    assert meta["sample_time_ms"] == pytest.approx(0.043)
    assert meta["energy_kv"] == 68.0
    assert meta["intensity_ma"] == pytest.approx(1.47)
    assert meta["data_offset_bytes"] == 512 * (extra_blocks + 1)
    assert meta["padding_size_bytes"] == (496 if padded else 0)
    assert meta == api.rad_info(path)
    assert path.read_bytes() == original


@pytest.mark.parametrize("damage", ["header", "magic", "type", "width", "depth", "extent", "offset", "negative_offset", "truncated", "extra", "nonzero_padding", "partial_padding"])
def test_rad_rejects_unsupported_or_corrupt_storage(tmp_path, damage):
    path = tmp_path / "bad.RAD"
    data = bytearray(_write_rad(path))
    if damage == "header":
        del data[100:]
    elif damage == "magic":
        data[:16] = b"Not a RAD header"
    elif damage in {"type", "width", "depth", "extent", "offset", "negative_offset"}:
        offset, value = {"type": (16, 2), "width": (44, 0), "depth": (52, 2),
                         "extent": (56, -1), "offset": (508, 10), "negative_offset": (508, -1)}[damage]
        struct.pack_into("<i", data, offset, value)
    elif damage == "truncated":
        del data[-1:]
    elif damage == "extra":
        data += b"\0" * 512
    elif damage == "nonzero_padding":
        data += b"\0" * 495 + b"\1"
    else:
        data += b"\0" * 2
    path.write_bytes(data)
    for reader in (api.read_rad, api.rad_info):
        with pytest.raises(ValueError, match="RAD"):
            reader(path)


def test_rad_dispatch_aliases_cli_and_vms_filename_versions(tmp_path, capsys):
    path = tmp_path / "scout.RAD;1"
    _write_rad(path)
    image, meta = api.ReadImage(path)
    assert image[0, 0] == -32768
    assert api.ImageInfo(path) == meta
    assert cli.main([str(path), "--format", "rad", "--indent", "0"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["format"] == "RAD"
    assert info["spacing"] == pytest.approx([0.06, 0.08, 1.0])


@pytest.mark.parametrize("kwargs", [{"unit": "hu"}, {"density": True}, {"mmap": True}])
def test_rad_dispatch_rejects_conversions_and_unsupported_options(tmp_path, kwargs):
    path = tmp_path / "scout.RAD"
    _write_rad(path)
    with pytest.raises(ValueError, match="RAD.*native"):
        api.read_image(path, **kwargs)
