"""Pure Python reader for Scanco SCV scout-view files."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import struct
import warnings

import numpy as np


SCV_PREFIX_SIZE = 2
SCV_HEADER_SIZE = 105
SCV_RECORD_START = SCV_PREFIX_SIZE + SCV_HEADER_SIZE
IDENTITY_DIRECTION_3D = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


@dataclass(frozen=True)
class _ScvRecord:
    position: float
    phase: int
    byte_count: int
    aux: int
    file_offset: int
    payload_offset: int
    payload_size: int
    decoded_size: int


def _strip_ascii(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("ascii", errors="ignore").strip()


def _unpack_from(fmt: str, data: bytes, offset: int):
    try:
        return struct.unpack_from(fmt, data, offset)[0]
    except struct.error as exc:
        raise ValueError("SCV file is truncated") from exc


def _unpack_vms_float(data: bytes, offset: int) -> float:
    raw = data[offset : offset + 4]
    if len(raw) != 4:
        raise ValueError("SCV file is truncated")
    reordered = raw[2:4] + raw[0:2]
    return struct.unpack("<f", reordered)[0] / 4.0


def _decode_profile(payload: bytes, *, width: int | None = None) -> list[int]:
    values: list[int] = []
    index = 0
    while index < len(payload):
        value = payload[index]
        if value & 0x80:
            if index + 1 >= len(payload):
                raise ValueError("SCV RLE profile is truncated")
            repeat = 256 - value
            if width is not None and len(values) + repeat > width:
                raise ValueError("SCV profile exceeds its declared width")
            values.extend([payload[index + 1]] * repeat)
            index += 1
        else:
            if width is not None and len(values) >= width:
                raise ValueError("SCV profile exceeds its declared width")
            values.append(value)
        index += 1
    if width is not None and len(values) != width:
        raise ValueError("SCV profile does not match its declared width")
    return values


def _parse_header(data: bytes) -> dict:
    if len(data) < SCV_RECORD_START:
        raise ValueError("SCV file is too small to contain a scout-view header")

    patient_name = _strip_ascii(data[2:42])
    dim_x_pixel = _unpack_from("<i", data, 66)
    dim_y_pixel = _unpack_from("<i", data, 70)
    compression_alg = _unpack_from("<i", data, 103)
    if dim_x_pixel <= 0 or dim_y_pixel <= 0 or compression_alg <= 0:
        raise ValueError(f"Unsupported SCV header: {patient_name}")

    return {
        "format": "SCV",
        "identifier": patient_name,
        "magic": patient_name,
        "patient_name": patient_name,
        "patient_index": _unpack_from("<i", data, 42),
        "measurement_number": _unpack_from("<i", data, 46),
        "measurement_index": _unpack_from("<i", data, 50),
        "measurement_time": (_unpack_from("<i", data, 54), _unpack_from("<i", data, 58)),
        "site": _unpack_from("<i", data, 62),
        "dim_x_pixel": dim_x_pixel,
        "dim_y_pixel": dim_y_pixel,
        "dim_x_mm": _unpack_vms_float(data, 74),
        "dim_y_mm": _unpack_vms_float(data, 78),
        "reference": data[82],
        "ref_line_mm": _unpack_vms_float(data, 83),
        "scanner_id": _unpack_from("<i", data, 87),
        "used_channel": _unpack_from("<i", data, 91),
        "scout_angle": _unpack_vms_float(data, 95),
        "scaling_factor": _unpack_vms_float(data, 99),
        "compression_alg": compression_alg,
        "record_start": SCV_RECORD_START,
    }


def _unwrap_vms_records(data: bytes) -> tuple[bytes, list[int]]:
    """Remove RMS length words/alignment, retaining physical profile offsets."""
    chunks: list[bytes] = []
    profile_offsets: list[int] = []
    offset = 0
    while offset < len(data):
        if offset + 2 > len(data):
            raise ValueError("SCV VMS record length is truncated")
        size = _unpack_from("<H", data, offset)
        start = offset + 2
        end = start + size
        aligned_end = end + size % 2
        if aligned_end > len(data):
            raise ValueError("SCV VMS record or alignment padding is truncated")
        # RMS word-aligns odd-length records; the extra byte is not data and
        # need not be zero (binary saveset extracts can retain any value).
        if not chunks:
            if size != SCV_RECORD_START:
                raise ValueError("Unsupported SCV VMS header record length")
        else:
            if size < 9 or _unpack_from("<H", data, start + 6) + 8 != size:
                raise ValueError("SCV VMS record length does not match its profile")
            profile_offsets.append(start)
        chunks.append(data[start:end])
        offset = aligned_end
    return b"".join(chunks), profile_offsets


def _parse_records(data: bytes, width: int) -> list[tuple[_ScvRecord, bytes]]:
    records: list[tuple[_ScvRecord, bytes]] = []
    offset = SCV_RECORD_START
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("SCV profile record is truncated")

        if _unpack_from("<H", data, offset) != 3:
            raise ValueError("Unsupported SCV profile record marker")
        phase = _unpack_from("<H", data, offset + 4)
        position = _unpack_vms_float(data, offset + 2)
        if not np.isfinite(position):
            raise ValueError("SCV profile position is not finite")
        byte_count = _unpack_from("<H", data, offset + 6)
        if byte_count < 1:
            raise ValueError("Invalid SCV profile byte count")

        payload_offset = offset + 8
        payload_size = byte_count
        next_offset = offset + 8 + byte_count
        if next_offset > len(data):
            raise ValueError("SCV profile extends beyond end of file")

        payload = data[payload_offset:next_offset]
        # Retain the historical raw-word field for metadata compatibility.
        # It is compressed pixel data, NOT an offset or a separate header.
        aux = int.from_bytes(payload[:2], "little")
        decoded_size = len(_decode_profile(payload, width=width))
        records.append(
            (
                _ScvRecord(
                    position=position,
                    phase=phase,
                    byte_count=byte_count,
                    aux=aux,
                    file_offset=offset,
                    payload_offset=payload_offset,
                    payload_size=payload_size,
                    decoded_size=decoded_size,
                ),
                payload,
            )
        )
        offset = next_offset

    if not records:
        raise ValueError("SCV file does not contain any profile records")
    return records


def _record_to_dict(record: _ScvRecord) -> dict:
    return {
        "position": record.position,
        "phase": record.phase,
        "byte_count": record.byte_count,
        "aux": record.aux,
        "file_offset": record.file_offset,
        "payload_offset": record.payload_offset,
        "payload_size": record.payload_size,
        "decoded_size": record.decoded_size,
    }


def _build_meta(path: str | Path, header: dict, records: list[tuple[_ScvRecord, bytes]]) -> dict:
    height = int(header["dim_y_pixel"])
    width = int(header["dim_x_pixel"])
    spacing = (
        float(header["dim_x_mm"]) / width if width else 1.0,
        float(header["dim_y_mm"]) / height if height else 1.0,
        1.0,
    )
    header_spacing = spacing
    row_positions = tuple(float(record.position) for record, _payload in records)
    steps = np.diff(row_positions)
    uniform_rows = bool(
        not steps.size or
        (np.all(steps > 0) and np.allclose(steps, np.median(steps), atol=3e-5, rtol=1e-4))
    )
    pixel_space = not uniform_rows or not all(np.isfinite(s) and s > 0 for s in spacing)
    geometry_warning = ""
    if pixel_space:
        spacing = (1.0, 1.0, 1.0)
        geometry_warning = (
            "SCV loaded in pixel space: repeated/nonuniform row coordinates or invalid "
            "header extents prevent reliable physical geometry. Do not use it for physical "
            "measurements or registration; use a calibrated RAD radiograph when available."
        )
    first_row_position_mm = float(records[0][0].position)
    position = (
        0,
        0 if pixel_space else int(first_row_position_mm / spacing[1]),
        0,
    )
    origin = tuple(position[i] * spacing[i] for i in range(3))
    meta = dict(header)
    meta.update(
        {
            "filename": str(path),
            "geometry_unit": "pixel" if pixel_space else "mm",
            "geometry_source": "pixel_index" if pixel_space else "ipl_header",
            "geometry_warning": geometry_warning,
            "header_spacing": header_spacing,
            "row_positions_mm": row_positions,
            "row_positions_uniform": uniform_rows,
            "header_dimensions": (height, width),
            "dimensions": (height, width),
            "position": position,
            "offset": (0, 0, 0),
            "element_size": spacing,
            "spacing": spacing,
            "origin": origin,
            "vtkbone_origin": tuple(origin[i] + spacing[i] / 2.0 for i in range(3)),
            "direction": IDENTITY_DIRECTION_3D,
            "record_count": len(records),
            "records": [_record_to_dict(record) for record, _payload in records],
            "unit": "native",
        }
    )
    return meta


def _read_scv_records(path: str | Path) -> tuple[dict, list[tuple[_ScvRecord, bytes]]]:
    data = Path(path).read_bytes()
    # A VMS variable-length header record wraps the 107-byte SCV header,
    # whose own two-byte prefix is 3. Stream exports omit the RMS wrapper.
    wrapped = data[:4] == b"\x6b\x00\x03\x00"
    if wrapped:
        data, profile_offsets = _unwrap_vms_records(data)
    header = _parse_header(data)
    records = _parse_records(data, int(header["dim_x_pixel"]))
    if len(records) > int(header["dim_y_pixel"]):
        raise ValueError("SCV has more profile records than its declared height")
    header["storage_format"] = "vms_variable_records" if wrapped else "stream"
    if wrapped:
        records = [
            (replace(record, file_offset=offset, payload_offset=offset + 8), payload)
            for (record, payload), offset in zip(records, profile_offsets, strict=True)
        ]
        header["record_start"] = profile_offsets[0]
    return header, records


def scv_info(path: str | Path) -> dict:
    """Read SCV scout-view metadata without loading the reconstructed image."""
    header, records = _read_scv_records(path)
    return _build_meta(path, header, records)


def read_scv(path: str | Path) -> tuple[np.ndarray, dict]:
    """Read stream or VMS-record Scanco SCV files as a 2D uint8 NumPy array."""
    header, records = _read_scv_records(path)
    meta = _build_meta(path, header, records)
    if meta["geometry_warning"]:
        warnings.warn(meta["geometry_warning"], UserWarning, stacklevel=2)

    height, width = meta["dimensions"]
    image = np.zeros((height, width), dtype=np.uint8)

    for row, (record, payload) in enumerate(records[:height]):
        image[row] = _decode_profile(payload, width=width)

    return image, meta
