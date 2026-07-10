"""Pure Python reader for Scanco SCV scout-view files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

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


def _decode_profile(payload: bytes) -> list[int]:
    values: list[int] = []
    index = 0
    while index < len(payload):
        value = payload[index]
        if value & 0x80 and index + 1 < len(payload):
            values.extend([payload[index + 1]] * (256 - value))
            index += 1
        else:
            values.append(value)
        index += 1
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


def _parse_records(data: bytes) -> list[tuple[_ScvRecord, bytes]]:
    records: list[tuple[_ScvRecord, bytes]] = []
    offset = SCV_RECORD_START
    while offset < len(data):
        if offset + 10 > len(data):
            raise ValueError("SCV profile record is truncated")

        phase = _unpack_from("<H", data, offset + 4)
        position = _unpack_from("<f", data, offset) / 4.0 + phase / 131072.0
        byte_count = _unpack_from("<H", data, offset + 6)
        aux = _unpack_from("<H", data, offset + 8)
        if byte_count < 2:
            raise ValueError("Invalid SCV profile byte count")

        payload_offset = offset + 10
        payload_size = byte_count - 2
        next_offset = offset + 8 + byte_count
        if next_offset > len(data):
            raise ValueError("SCV profile extends beyond end of file")

        payload = data[payload_offset:next_offset]
        decoded_size = len(_decode_profile(payload))
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
    first_row_position_mm = float(records[0][0].position)
    position = (
        0,
        int(first_row_position_mm / spacing[1]) if spacing[1] else 0,
        0,
    )
    origin = tuple(position[i] * spacing[i] for i in range(3))
    meta = dict(header)
    meta.update(
        {
            "filename": str(path),
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


def scv_info(path: str | Path) -> dict:
    """Read SCV scout-view metadata without loading the reconstructed image."""
    data = Path(path).read_bytes()
    header = _parse_header(data)
    records = _parse_records(data)
    return _build_meta(path, header, records)


def read_scv(path: str | Path) -> tuple[np.ndarray, dict]:
    """Read a Scanco SCV scout-view file as a 2D uint8 NumPy array."""
    data = Path(path).read_bytes()
    header = _parse_header(data)
    records = _parse_records(data)
    meta = _build_meta(path, header, records)

    height, width = meta["dimensions"]
    image = np.zeros((height, width), dtype=np.uint8)

    for row, (record, payload) in enumerate(records[:height]):
        profile = np.asarray(_decode_profile(payload), dtype=np.uint8)
        left = max(0, 256 - int(record.aux))
        right = min(width, left + profile.size)
        if right <= left:
            continue
        image[row, left:right] = profile[: right - left]

    return image, meta
