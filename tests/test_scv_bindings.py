import struct
from pathlib import Path

import numpy as np
import pytest

import py_aimio as api


def _vms_float(value):
    raw = struct.pack("<f", value * 4.0)
    return raw[2:4] + raw[0:2]


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
        (b"\x01\xfd\x02\xfe\x03\xfe\x00", [1, 2, 2, 2, 3, 3, 0, 0]),
        (b"\xfe\x00\xfe\x04\x05\xfd\x06", [0, 0, 4, 4, 5, 6, 6, 6]),
        (b"\xfc\x00\x07\xfe\x08\x09", [0, 0, 0, 0, 7, 8, 8, 9]),
    ]
    payload = bytearray(header)
    for row, (encoded, _profile) in enumerate(profiles):
        payload += b"\x03\x00" + _vms_float(100.0 + row)
        payload += struct.pack("<H", len(encoded))
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
    assert info["records"][0]["aux"] == 64769  # Raw first two RLE bytes, not an offset.
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
    for row, (_encoded, profile) in enumerate(profiles):
        expected[row] = profile
    assert np.array_equal(image, expected)


def _wrap_scv_vms_records(data):
    """Add RMS lengths and even-byte alignment to independent SCV records."""
    chunks = [data[:107]]
    offset = 107
    while offset < len(data):
        count = struct.unpack_from("<H", data, offset + 6)[0]
        end = offset + 8 + count
        chunks.append(data[offset:end])
        offset = end
    return b"".join(
        struct.pack("<H", len(chunk)) + chunk + (b"\x00" if len(chunk) % 2 else b"")
        for chunk in chunks
    )


def _write_wrapped_scv(path):
    _write_scv(path)
    header = path.read_bytes()[:107]
    # Two odd-sized 15-byte records followed by one even-sized 14-byte record.
    profiles = [b"\x01\xfd\x02\xfe\x03\xfe\x00",
                b"\xfe\x00\xfe\x04\x05\xfd\x06",
                b"\xfc\x00\x07\xfe\x08\x09"]
    stream = header + b"".join(
        b"\x03\x00" + _vms_float(100.0 + row) + struct.pack("<H", len(payload)) + payload
        for row, payload in enumerate(profiles)
    )
    wrapped = _wrap_scv_vms_records(stream)
    path.write_bytes(wrapped)
    return wrapped


@pytest.mark.parametrize("alignment_byte", [0, 1, 255])
def test_scv_reads_vms_variable_records_without_changing_the_source(tmp_path, alignment_byte):
    path = tmp_path / "wrapped.SCV"
    wrapped = bytearray(_write_wrapped_scv(path))
    wrapped[109] = wrapped[127] = wrapped[145] = alignment_byte
    path.write_bytes(wrapped)

    image, info = api.read_scv(path)

    expected = np.array([
        [1, 2, 2, 2, 3, 3, 0, 0],
        [0, 0, 4, 4, 5, 6, 6, 6],
        [0, 0, 0, 0, 7, 8, 8, 9],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
    ], dtype=np.uint8)
    assert np.array_equal(image, expected)
    assert info["dimensions"] == (6, 8)
    assert info["storage_format"] == "vms_variable_records"
    assert info["record_start"] == 112
    assert [record["file_offset"] for record in info["records"]] == [112, 130, 148]
    assert info["records"][0]["payload_offset"] == 120
    assert wrapped[120:127] == b"\x01\xfd\x02\xfe\x03\xfe\x00"
    assert api.scv_info(path)["record_count"] == 3
    assert path.read_bytes() == wrapped


@pytest.mark.parametrize("damage", ["truncated", "length", "header_pad", "profile_pad", "trailing"])
def test_scv_rejects_malformed_vms_variable_records(tmp_path, damage):
    path = tmp_path / "bad_wrapped.SCV"
    data = bytearray(_write_wrapped_scv(path))
    if damage == "truncated":
        del data[-1:]  # Truncated final profile body.
    elif damage == "length":
        struct.pack_into("<H", data, 110, 14)  # Inner SCV record still declares 15 bytes.
    elif damage == "header_pad":
        del data[109]
    elif damage == "profile_pad":
        del data[127]
    else:
        data += b"\x00"
    path.write_bytes(data)

    with pytest.raises(ValueError, match="VMS|record|padding|truncated"):
        api.read_scv(path)


def test_scv_rejects_unsupported_magic(tmp_path):
    path = tmp_path / "not_scv.SCV"
    path.write_bytes(b"\x03\x00NOT_SCV".ljust(107, b"\0"))

    with pytest.raises(ValueError, match="Unsupported SCV header"):
        api.scv_info(path)


def _write_native_scv(path, positions, payloads, *, wrapped=False):
    """Build native records: marker, F-float coordinate, size, full RLE row."""
    header = bytearray(107)
    header[:2] = b"\x03\x00"
    header[2:42] = b"Synthetic scout".ljust(40, b" ")
    struct.pack_into("<ii", header, 66, 8, len(positions))
    header[74:78] = _vms_float(8.0)
    header[78:82] = _vms_float(6.0)
    struct.pack_into("<i", header, 103, 1)
    records = [
        b"\x03\x00" + _vms_float(position) + struct.pack("<H", len(payload)) + payload
        for position, payload in zip(positions, payloads, strict=True)
    ]
    data = bytes(header) + b"".join(records)
    path.write_bytes(_wrap_scv_vms_records(data) if wrapped else data)


@pytest.mark.parametrize("positions", [[140.0, 140.0, 140.063], [140.0, 140.063, 140.190]])
@pytest.mark.parametrize("wrapped", [False, True])
def test_scv_uncertain_row_geometry_uses_explicit_pixel_space(tmp_path, positions, wrapped):
    path = tmp_path / "uncertain.SCV"
    _write_native_scv(path, positions, [b"\xf8\x01"] * 3, wrapped=wrapped)

    info = api.scv_info(path)
    assert info["geometry_unit"] == "pixel"
    assert info["geometry_source"] == "pixel_index"
    assert info["spacing"] == (1.0, 1.0, 1.0)
    assert info["origin"] == (0.0, 0.0, 0.0)
    assert info["row_positions_mm"] == pytest.approx(positions, abs=2e-5)
    with pytest.warns(UserWarning, match="pixel space.*measurements"):
        image, meta = api.read_scv(path)
    assert image.shape == (3, 8)
    assert np.all(image == 1)
    assert meta == info


@pytest.mark.parametrize("wrapped", [False, True])
def test_scv_decodes_the_first_two_compressed_bytes_as_pixels(tmp_path, wrapped):
    path = tmp_path / "full_rows.SCV"
    _write_native_scv(path, [140.0, 140.5], [
        b"\x4d\x4f\xfa\x50",  # 77, 79, then six 80s; no leading zero run.
        b"\xfb\x40\x41\x42\x43",  # Five 64s, then 65, 66, 67.
    ], wrapped=wrapped)

    image, meta = api.read_scv(path)

    assert image.tolist() == [[77, 79, 80, 80, 80, 80, 80, 80],
                              [64, 64, 64, 64, 64, 65, 66, 67]]
    assert [r["decoded_size"] for r in meta["records"]] == [8, 8]
    with path.open("rb") as source:
        source.seek(meta["records"][0]["payload_offset"])
        assert source.read(2) == b"\x4d\x4f"


@pytest.mark.parametrize("position", [90.0857, 140.063, 165.079, -140.063])
def test_scv_reads_record_coordinates_as_complete_vms_floats(tmp_path, position):
    path = tmp_path / "position.SCV"
    _write_native_scv(path, [position], [b"\xf8\x01"])

    meta = api.scv_info(path)

    assert meta["records"][0]["position"] == pytest.approx(position, abs=2e-5)


@pytest.mark.parametrize("payload", [b"\x01\xff", b"\xf7\x01", b"\xf9\x01"])
def test_scv_rejects_truncated_or_wrong_width_rle_rows(tmp_path, payload):
    path = tmp_path / "bad_rle.SCV"
    _write_native_scv(path, [90.0], [payload])

    with pytest.raises(ValueError, match="profile|width|RLE|truncated"):
        api.read_scv(path)


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
