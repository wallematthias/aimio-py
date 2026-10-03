"""RSQ storage contracts exercised entirely with synthetic files."""

import builtins
import io
import struct

import numpy as np
import pytest

import py_aimio as api


COUNTS = np.array(
    [
        [[0, 1, 65535], [100, 101, 102], [200, 201, 202], [300, 301, 302]],
        [[1000, 1001, 1002], [1100, 1101, 1102], [1200, 1201, 1202], [1300, 1301, 1302]],
    ],
    dtype="<u2",
)


def write_rsq(path, *, counts=COUNTS, extra_blocks=2, calibration=None, words=None):
    """Build an independent minimal CTDATA storage fixture, never real headers."""
    header = bytearray(512 * (extra_blocks + 1))
    header[:16] = b"CTDATA-HEADER_V1"
    values = {
        11: counts.shape[2], 12: counts.shape[1], 13: counts.shape[0],
        15: 360000, 17: 82, 18: 82, 19: 15000, 21: 0, 22: 65535,
        23: 6, 24: 4, 25: 600, 26: 400, 29: 100000, 30: 50000,
        49: 2, 65: 2, 127: extra_blocks,
    }
    values.update(words or {})
    for index, value in values.items():
        struct.pack_into("<I", header, index * 4, value)
    # This synthetic patient field must never be decoded as a metadata key.
    header[160:181] = b"SYNTHETIC NAME ONLY!!"
    if calibration is not None:
        title, coefficients, anchors = calibration
        start = extra_blocks * 512
        header[start:start + len(title)] = title
        text = f"Corr at 2 3 6: {anchors[0]} {anchors[1]} {anchors[2]}".encode("ascii")
        header[start + 48:start + 48 + len(text)] = text
        struct.pack_into("<3d", header, start + 476, *coefficients)
    path.write_bytes(header + counts.astype("<u2").tobytes(order="C"))
    return path


@pytest.mark.parametrize("mmap", [False, True])
def test_read_rsq_preserves_unsigned_counts_and_row_frame_column_order(tmp_path, mmap):
    path = write_rsq(tmp_path / "synthetic.RSQ")

    counts, meta = api.read_rsq(path, mmap=mmap)

    assert np.array_equal(counts, COUNTS)
    assert counts.dtype.str == "<u2"
    assert counts[0, 0, 2] == 65535
    assert meta["shape"] == (2, 4, 3)
    assert meta["axis_order"] == ("detector_row", "frame", "detector_column")
    assert meta["dtype"] == "<u2"
    assert meta["data_offset_bytes"] == 1536
    assert meta["format"] == "RSQ"
    assert meta["unit"] == "detector_counts"
    assert isinstance(counts, np.memmap) is mmap
    if mmap:
        assert not counts.flags.writeable
        with pytest.raises(ValueError):
            counts[0, 0, 0] = 99


def test_rsq_reads_without_native_extension_and_retains_single_frame(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "_aimio", None)
    path = write_rsq(tmp_path / "single.RSQ", counts=COUNTS[:, :1, :])

    counts, _ = api.read_rsq(path)

    assert counts.shape == (2, 1, 3)
    assert np.array_equal(counts, COUNTS[:, :1, :])


def test_rsq_info_reports_raw_header_and_geometry_without_spatial_volume_keys(tmp_path):
    info = api.rsq_info(write_rsq(tmp_path / "geometry.RSQ"))

    assert len(info["header_words"]) == 128
    assert all(isinstance(word, int) for word in info["header_words"])
    assert info["header_words"][11:14] == (3, 4, 2)
    assert info["dimensions"] == (2, 4, 3)
    assert info["geometry"]["requested_spacing_um"] == (82, 82)
    assert info["geometry"]["axial_start_um"] == 15000
    assert info["geometry"]["native_horizontal_samples"] == 6
    assert info["geometry"]["active_native_rows"] == 4
    assert info["geometry"]["detector_width_um"] == 600
    assert info["geometry"]["detector_height_um"] == 400
    assert info["geometry"]["source_detector_distance_um"] == 100000
    assert info["geometry"]["source_axis_distance_um"] == 50000
    assert info["geometry"]["binning"] == 2
    assert info["geometry"]["object_view_count"] == 2
    assert info["geometry"]["angular_interval_mdeg"] == 360000
    assert info["geometry"]["angular_step_mdeg"] == 180000
    assert "inferred" in info["geometry"]["provenance"].lower()
    assert info["count_range"] == (0, 65535)
    assert not {"patient_name", "spacing", "origin", "direction", "mu_scaling"} & info.keys()


def test_rsq_info_does_not_read_payload(tmp_path, monkeypatch):
    path = write_rsq(tmp_path / "headers_only.RSQ")
    real_open = builtins.open
    reads = []

    class HeaderOnlyFile:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def __getattr__(self, name):
            return getattr(self.handle, name)

        def read(self, size=-1):
            position = self.handle.tell()
            assert size >= 0 and position + size <= 1536, "rsq_info read the payload"
            reads.append((position, size))
            return self.handle.read(size)

    def guarded_open(*args, **kwargs):
        return HeaderOnlyFile(real_open(*args, **kwargs))

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)

    info = api.rsq_info(path)

    assert info["shape"] == (2, 4, 3)
    assert reads
    assert sum(size for _, size in reads) <= 1024


@pytest.mark.parametrize("magic", [b"CTDATA-HEADER_V2", b"NOT-AN-RSQ-FILE!"])
def test_rsq_rejects_unsupported_magic(tmp_path, magic):
    path = write_rsq(tmp_path / "unsupported.RSQ")
    data = bytearray(path.read_bytes())
    data[:16] = magic
    path.write_bytes(data)

    with pytest.raises(ValueError, match="magic|CTDATA|Unsupported"):
        api.read_rsq(path)


@pytest.mark.parametrize("dimension_word", [11, 12, 13])
def test_rsq_rejects_zero_dimensions(tmp_path, dimension_word):
    path = write_rsq(tmp_path / "zero.RSQ", words={dimension_word: 0})

    with pytest.raises(ValueError, match="dimension|shape"):
        api.rsq_info(path)


@pytest.mark.parametrize("word,value", [(127, 0xFFFFFFFF), (11, 0xFFFFFFFF)])
def test_rsq_rejects_impossible_offsets_and_shapes_without_allocation(tmp_path, word, value):
    path = write_rsq(tmp_path / "impossible.RSQ", words={word: value})

    with pytest.raises(ValueError, match="offset|payload|size|header"):
        api.read_rsq(path)


@pytest.mark.parametrize("byte_change", [-1, 1, 2])
@pytest.mark.parametrize("reader", ["read_rsq", "rsq_info"])
def test_rsq_rejects_truncated_and_trailing_payload(tmp_path, byte_change, reader):
    path = write_rsq(tmp_path / "bad_payload.RSQ")
    data = path.read_bytes()
    path.write_bytes(data[:byte_change] if byte_change < 0 else data + b"\x00" * byte_change)

    with pytest.raises(ValueError, match="payload|size"):
        getattr(api, reader)(path)


def test_rsq_rejects_truncated_base_header(tmp_path):
    path = tmp_path / "short.RSQ"
    path.write_bytes(b"CTDATA-HEADER_V1")

    with pytest.raises(ValueError, match="header|small|truncated"):
        api.rsq_info(path)


def test_rsq_reads_without_extra_header_blocks(tmp_path):
    path = write_rsq(tmp_path / "base_only.RSQ", extra_blocks=0)

    counts, info = api.read_rsq(path)

    assert np.array_equal(counts, COUNTS)
    assert info["data_offset_bytes"] == 512
    assert info["beam_hardening"]["available"] is False


@pytest.mark.parametrize("title", [b"Beamhard.Corr.", b"PREFIX__Beamhard.Corr."])
def test_rsq_validates_recognized_beam_hardening_coefficients(tmp_path, title):
    path = write_rsq(
        tmp_path / "calibrated.RSQ",
        calibration=(title, (0.125, -0.01, 0.001), (0.218, 0.312, 0.606)),
    )

    info = api.rsq_info(path)

    assert info["beam_hardening"]["available"] is True
    assert info["beam_hardening"]["coefficients"] == (0.125, -0.01, 0.001)
    assert info["beam_hardening"]["anchors"] == (0.218, 0.312, 0.606)
    assert "a1" in info["beam_hardening"]["polynomial"]


@pytest.mark.parametrize("coefficients,anchors", [
    ((0.125, -0.01, 0.001), (0.219, 0.312, 0.606)),
    ((float("nan"), 0, 0), (0, 0, 0)),
    ((float("inf"), 0, 0), (0, 0, 0)),
])
def test_rsq_rejects_corrupt_recognized_calibration(tmp_path, coefficients, anchors):
    path = write_rsq(tmp_path / "corrupt.RSQ", calibration=(b"Beamhard.Corr.", coefficients, anchors))

    with pytest.raises(ValueError, match="calibration|beam.hardening|Beam.hardening"):
        api.rsq_info(path)


def test_rsq_rejects_recognized_calibration_missing_printed_anchors(tmp_path):
    path = write_rsq(
        tmp_path / "missing_anchors.RSQ",
        calibration=(b"Beamhard.Corr.", (0.125, -0.01, 0.001), (0.218, 0.312, 0.606)),
    )
    data = bytearray(path.read_bytes())
    data[1072:1200] = b"\x00" * 128
    path.write_bytes(data)

    with pytest.raises(ValueError, match="calibration|anchor|Beam.hardening"):
        api.rsq_info(path)


@pytest.mark.parametrize("calibration", [None, (b"Other calibration", (0, 0, 0), (0, 0, 0))])
def test_rsq_explicitly_marks_missing_or_unrecognized_calibration_unavailable(tmp_path, calibration):
    info = api.rsq_info(write_rsq(tmp_path / "uncalibrated.RSQ", calibration=calibration))

    assert info["beam_hardening"]["available"] is False
    assert info["beam_hardening"]["reason"]
    assert "coefficients" not in info["beam_hardening"]


def test_rsq_does_not_fabricate_angle_step_when_object_view_count_is_unavailable(tmp_path):
    info = api.rsq_info(write_rsq(tmp_path / "no_views.RSQ", words={65: 0}))

    assert info["geometry"]["angular_step_mdeg"] is None
