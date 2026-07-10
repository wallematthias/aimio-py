"""Pure Python reader for Scanco GOBJ contour mask files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

import numpy as np


CTDATA_MAGIC = b"CTDATA-HEADER_V1"
CTDATA_HEADER_SIZE = 512
GOBJ_DATA_TYPE = 6
SLICE_RECORD_KIND = 20
CONTOUR_RECORD_KIND = 32
SUBTRACTIVE_MATERIAL = 3
DEFAULT_MASK_VALUE = 127
SUPPORTED_CROPS = {"tight", "header"}
IDENTITY_DIRECTION_3D = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
CHAIN_DIRECTIONS = (
    (0, 1),
    (1, 1),
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, -1),
    (-1, 0),
    (-1, 1),
)


@dataclass(frozen=True)
class _GobjContour:
    file_offset: int
    payload_offset: int
    header_size: int
    material: int
    center_x: int
    center_y: int
    z: int
    width: int
    height: int
    start_y: int
    start_x_relative: int
    step_count: int
    byte_count: int


@dataclass(frozen=True)
class _GobjPrimitive:
    file_offset: int
    payload_offset: int
    header_size: int
    shape: int
    center_x: int
    center_y: int
    z: int
    width: int
    height: int


@dataclass(frozen=True)
class _GobjSlice:
    file_offset: int
    center_x: int
    center_y: int
    z: int
    width: int
    height: int
    primitives: tuple[_GobjPrimitive, ...]
    contours: tuple[_GobjContour, ...]
    drawables: tuple[_GobjPrimitive | _GobjContour, ...]


def _unpack_from(fmt: str, data: bytes, offset: int):
    try:
        return struct.unpack_from(fmt, data, offset)
    except struct.error as exc:
        raise ValueError("GOBJ file is truncated") from exc


def _parse_header(data: bytes) -> dict:
    if len(data) < CTDATA_HEADER_SIZE:
        raise ValueError("GOBJ file is too small to contain a CTDATA header")
    if data[: len(CTDATA_MAGIC)] != CTDATA_MAGIC:
        raise ValueError("Unsupported GOBJ header")

    data_type = _unpack_from("<i", data, 16)[0]
    if data_type != GOBJ_DATA_TYPE:
        raise ValueError(f"Expected GOBJ data type 6, found {data_type}")

    dim_x, dim_y, dim_z = _unpack_from("<3i", data, 32)
    dim_x_um, dim_y_um, dim_z_um = _unpack_from("<3i", data, 44)
    data_offset_blocks = _unpack_from("<i", data, 508)[0]
    data_offset = CTDATA_HEADER_SIZE + max(0, data_offset_blocks) * CTDATA_HEADER_SIZE

    spacing = (
        dim_x_um / dim_x / 1000.0 if dim_x else 1.0,
        dim_y_um / dim_y / 1000.0 if dim_y else 1.0,
        dim_z_um / dim_z / 1000.0 if dim_z else 1.0,
    )
    return {
        "format": "GOBJ",
        "data_type": data_type,
        "header_dimensions": (dim_x, dim_y, dim_z),
        "header_dimensions_um": (dim_x_um, dim_y_um, dim_z_um),
        "data_offset": data_offset,
        "element_size": spacing,
        "spacing": spacing,
    }


def _is_slice_header(data: bytes, offset: int) -> bool:
    if offset > len(data) - 52:
        return False
    fields = _unpack_from("<13i", data, offset)
    return (
        fields[0] == 1
        and fields[7] == 3
        and fields[8] == SLICE_RECORD_KIND
        and fields[9] == 0
        and fields[10] == 0
        and fields[11] == 16512
        and fields[12] == 16512
    )


def _parse_contour(data: bytes, offset: int, first: bool) -> _GobjContour | None:
    if first and offset <= len(data) - 72:
        fields = _unpack_from("<18i", data, offset)
        if (
            fields[0] != 0
            and fields[1] == 3
            and fields[8] == 3
            and fields[9] == CONTOUR_RECORD_KIND
            and fields[12] == 16512
            and fields[13] == 16512
            and fields[16] >= 0
            and fields[17] >= 0
        ):
            return _GobjContour(
                file_offset=offset,
                payload_offset=offset,
                header_size=72,
                material=fields[0],
                center_x=fields[2],
                center_y=fields[3],
                z=fields[4],
                width=fields[5],
                height=fields[6],
                start_y=fields[14],
                start_x_relative=fields[15],
                step_count=fields[16],
                byte_count=fields[17],
            )

    if offset <= len(data) - 68:
        fields = _unpack_from("<17i", data, offset)
        if (
            fields[6] == 0
            and fields[7] == 3
            and fields[8] == CONTOUR_RECORD_KIND
            and fields[11] == 16512
            and fields[12] == 16512
            and fields[15] >= 0
            and fields[16] >= 0
        ):
            return _GobjContour(
                file_offset=offset,
                payload_offset=offset,
                header_size=68,
                material=fields[0],
                center_x=fields[1],
                center_y=fields[2],
                z=fields[3],
                width=fields[4],
                height=fields[5],
                start_y=fields[13],
                start_x_relative=fields[14],
                step_count=fields[15],
                byte_count=fields[16],
            )
    return None


def _parse_primitive(data: bytes, offset: int, first: bool) -> _GobjPrimitive | None:
    if first and offset <= len(data) - 40:
        fields = _unpack_from("<10i", data, offset)
        if fields[7] == 0 and fields[8] == 3 and fields[9] == 0 and fields[4] >= 0 and fields[5] >= 0:
            return _GobjPrimitive(
                file_offset=offset,
                payload_offset=offset,
                header_size=40,
                shape=fields[1],
                center_x=fields[2],
                center_y=fields[3],
                z=fields[4],
                width=fields[5],
                height=fields[6],
            )

    if offset <= len(data) - 36:
        fields = _unpack_from("<9i", data, offset)
        if fields[6] == 0 and fields[7] == 3 and fields[8] == 0 and fields[3] >= 0 and fields[4] >= 0 and fields[5] >= 0:
            return _GobjPrimitive(
                file_offset=offset,
                payload_offset=offset,
                header_size=36,
                shape=fields[0],
                center_x=fields[1],
                center_y=fields[2],
                z=fields[3],
                width=fields[4],
                height=fields[5],
            )
    return None


def _next_slice_offset(payload: bytes, offset: int) -> int:
    for index in range(offset, len(payload) - 52 + 1):
        if _is_slice_header(payload, index):
            return index
    return len(payload)


def _find_next_drawable(
    payload: bytes,
    offset: int,
    stop: int,
    first: bool,
) -> _GobjPrimitive | _GobjContour | None:
    index = offset
    while index < stop:
        primitive = _parse_primitive(payload, index, first)
        if primitive is not None and index + primitive.header_size <= stop:
            return primitive
        contour = _parse_contour(payload, index, first)
        if contour is not None and index + contour.header_size + contour.byte_count <= stop:
            return contour
        index += 1
    return None


def _parse_slices(data: bytes, data_offset: int) -> list[_GobjSlice]:
    payload = data[data_offset:]
    offset = 0
    slices: list[_GobjSlice] = []
    while offset < len(payload) - 52:
        if all(value == 0 for value in payload[offset:]):
            break
        if not _is_slice_header(payload, offset):
            raise ValueError(f"Unsupported GOBJ contour structure at byte {data_offset + offset}")

        fields = _unpack_from("<13i", payload, offset)
        slice_offset = data_offset + offset
        offset += 52
        next_slice_offset = _next_slice_offset(payload, offset)
        contours: list[_GobjContour] = []
        primitives: list[_GobjPrimitive] = []
        drawables: list[_GobjPrimitive | _GobjContour] = []
        first = True
        while offset < next_slice_offset:
            drawable = _find_next_drawable(payload, offset, next_slice_offset, first)
            if drawable is None:
                break
            if isinstance(drawable, _GobjContour):
                drawable = _GobjContour(
                    file_offset=data_offset + drawable.file_offset,
                    payload_offset=drawable.payload_offset,
                    header_size=drawable.header_size,
                    material=drawable.material,
                    center_x=drawable.center_x,
                    center_y=drawable.center_y,
                    z=drawable.z,
                    width=drawable.width,
                    height=drawable.height,
                    start_y=drawable.start_y,
                    start_x_relative=drawable.start_x_relative,
                    step_count=drawable.step_count,
                    byte_count=drawable.byte_count,
                )
                contours.append(drawable)
                offset = drawable.payload_offset + drawable.header_size + drawable.byte_count
            else:
                drawable = _GobjPrimitive(
                    file_offset=data_offset + drawable.file_offset,
                    payload_offset=drawable.payload_offset,
                    header_size=drawable.header_size,
                    shape=drawable.shape,
                    center_x=drawable.center_x,
                    center_y=drawable.center_y,
                    z=drawable.z,
                    width=drawable.width,
                    height=drawable.height,
                )
                primitives.append(drawable)
                offset = drawable.payload_offset + drawable.header_size
            drawables.append(drawable)
            first = False
        offset = next_slice_offset

        if not drawables:
            if fields[4] == 0 and fields[5] == 0:
                continue
            raise ValueError(f"GOBJ slice at byte {slice_offset} does not contain contours")
        slices.append(
            _GobjSlice(
                file_offset=slice_offset,
                center_x=fields[1],
                center_y=fields[2],
                z=fields[3],
                width=fields[4],
                height=fields[5],
                primitives=tuple(primitives),
                contours=tuple(contours),
                drawables=tuple(drawables),
            )
        )

    if not slices:
        raise ValueError("GOBJ file does not contain any contour slices")
    return slices


def _contour_bbox(contour: _GobjContour) -> tuple[int, int, int, int]:
    xmin = contour.center_x - (contour.width - 1) // 2
    ymin = contour.center_y - (contour.height - 1) // 2
    return xmin, ymin, xmin + contour.width - 1, ymin + contour.height - 1


def _drawable_bbox(drawable: _GobjPrimitive | _GobjContour) -> tuple[int, int, int, int]:
    xmin = drawable.center_x - (drawable.width - 1) // 2
    ymin = drawable.center_y - (drawable.height - 1) // 2
    return xmin, ymin, xmin + drawable.width - 1, ymin + drawable.height - 1


def _unpack_3bit(payload: bytes, count: int) -> list[int]:
    values: list[int] = []
    accumulator = 0
    bits = 0
    for byte in payload:
        accumulator |= byte << bits
        bits += 8
        while bits >= 3 and len(values) < count:
            values.append(accumulator & 0x07)
            accumulator >>= 3
            bits -= 3
    if not values and count:
        raise ValueError("GOBJ contour chain is truncated")
    return values


def _decode_contour_points(payload_data: bytes, contour: _GobjContour, position: tuple[int, int, int]) -> np.ndarray:
    payload_offset = contour.payload_offset + contour.header_size
    payload = payload_data[payload_offset : payload_offset + contour.byte_count]
    values = _unpack_3bit(payload, contour.step_count)

    start_y = contour.center_y + contour.start_y - position[1]
    start_x = contour.center_x + contour.start_x_relative - position[0]
    y = start_y
    x = start_x
    points = []
    for value in values:
        dy, dx = CHAIN_DIRECTIONS[(value + 2) % 8]
        y += dy
        x += dx
        points.append((y, x))

    raw_points = np.asarray(points, dtype=int)
    points = np.column_stack(
        [
            start_y + (raw_points[:, 1] - start_x),
            start_x + (raw_points[:, 0] - start_y),
        ]
    )

    xmin, ymin, _xmax, _ymax = _contour_bbox(contour)
    shift_y = ymin - position[1] - int(points[:, 0].min())
    shift_x = xmin - position[0] - int(points[:, 1].min())
    return points + np.array([shift_y, shift_x])


def _draw_line(mask: np.ndarray, start: tuple[int, int], end: tuple[int, int]) -> None:
    y0, x0 = start
    y1, x1 = end
    dy = abs(y1 - y0)
    dx = abs(x1 - x0)
    steps = max(dy, dx)
    if steps == 0:
        if 0 <= y0 < mask.shape[0] and 0 <= x0 < mask.shape[1]:
            mask[y0, x0] = True
        return
    for index in range(steps + 1):
        y = round(y0 + (y1 - y0) * index / steps)
        x = round(x0 + (x1 - x0) * index / steps)
        if 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1]:
            mask[y, x] = True


def _rasterize_filled_contour(shape: tuple[int, int], points: np.ndarray) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)
    point_list = [(int(y), int(x)) for y, x in points]
    for start, end in zip(point_list, point_list[1:] + point_list[:1]):
        _draw_line(mask, start, end)

    if not point_list:
        return mask

    height, width = shape
    y_min = max(0, min(y for y, _x in point_list))
    y_max = min(height - 1, max(y for y, _x in point_list))
    edges = list(zip(point_list, point_list[1:] + point_list[:1]))
    for y in range(y_min, y_max + 1):
        scan_y = y + 0.5
        intersections: list[float] = []
        for (y0, x0), (y1, x1) in edges:
            if y0 == y1:
                continue
            if (y0 <= scan_y < y1) or (y1 <= scan_y < y0):
                intersections.append(x0 + (scan_y - y0) * (x1 - x0) / (y1 - y0))
        intersections.sort()
        for left, right in zip(intersections[0::2], intersections[1::2]):
            x0 = max(0, int(np.ceil(left)))
            x1 = min(width - 1, int(np.floor(right)))
            if x1 >= x0:
                mask[y, x0 : x1 + 1] = True

    return mask


def _strict_interior(mask: np.ndarray) -> np.ndarray:
    """Return filled pixels that are not on the 4-connected contour boundary."""
    padded = np.pad(mask, 1, constant_values=False)
    return (
        mask
        & padded[:-2, 1:-1]
        & padded[2:, 1:-1]
        & padded[1:-1, :-2]
        & padded[1:-1, 2:]
    )


def _rasterize_primitive(shape: tuple[int, int], primitive: _GobjPrimitive, position: tuple[int, int, int]) -> np.ndarray:
    height, width = shape
    xmin, ymin, xmax, ymax = _drawable_bbox(primitive)
    x0 = xmin - position[0]
    x1 = xmax - position[0]
    y0 = ymin - position[1]
    y1 = ymax - position[1]
    mask = np.zeros(shape, dtype=bool)
    if primitive.shape == 4:
        mask[max(0, y0) : min(height, y1 + 1), max(0, x0) : min(width, x1 + 1)] = True
        return mask
    if primitive.shape == 6:
        yy, xx = np.ogrid[:height, :width]
        cx = primitive.center_x - position[0]
        cy = primitive.center_y - position[1]
        rx = max(primitive.width / 2.0, 0.5)
        ry = max(primitive.height / 2.0, 0.5)
        return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0
    return mask


def _is_slice_parent(drawable: _GobjPrimitive | _GobjContour, image_slice: _GobjSlice) -> bool:
    return (
        drawable.center_x == image_slice.center_x
        and drawable.center_y == image_slice.center_y
        and drawable.width == image_slice.width
        and drawable.height == image_slice.height
    )


def _is_subtractive_drawable(
    drawable: _GobjPrimitive | _GobjContour,
    image_slice: _GobjSlice,
    index: int,
) -> bool:
    if index == 0:
        return False
    if image_slice.drawables and _is_slice_parent(image_slice.drawables[0], image_slice):
        return True
    materials = {contour.material for contour in image_slice.contours}
    return isinstance(drawable, _GobjContour) and drawable.material == SUBTRACTIVE_MATERIAL and len(materials) > 1


def _contour_extent(slices: list[_GobjSlice]) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    boxes = [_drawable_bbox(drawable) for image_slice in slices for drawable in image_slice.drawables]
    z_values = [image_slice.z for image_slice in slices]
    xmin = min(box[0] for box in boxes)
    ymin = min(box[1] for box in boxes)
    xmax = max(box[2] for box in boxes)
    ymax = max(box[3] for box in boxes)
    zmin = min(z_values)
    zmax = max(z_values)
    return (xmin, ymin, zmin), (xmax - xmin + 1, ymax - ymin + 1, zmax - zmin + 1)


def _output_geometry(header: dict, slices: list[_GobjSlice], crop: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    if crop == "tight":
        return _contour_extent(slices)
    header_dimensions = tuple(int(value) for value in header["header_dimensions"])
    z_values = [image_slice.z for image_slice in slices]
    return (0, 0, min(z_values)), header_dimensions


def _validate_raster_options(crop: str, value: int) -> None:
    if crop not in SUPPORTED_CROPS:
        raise ValueError("crop must be one of: 'tight' or 'header'")
    if not 0 <= int(value) <= 255:
        raise ValueError("value must fit into uint8: 0..255")


def _build_meta(
    path: str | Path,
    header: dict,
    slices: list[_GobjSlice],
    crop: str = "tight",
    value: int = DEFAULT_MASK_VALUE,
) -> dict:
    position, dimensions = _output_geometry(header, slices, crop)
    spacing = tuple(header["spacing"])
    origin = tuple(position[index] * spacing[index] for index in range(3))
    materials = sorted({contour.material for image_slice in slices for contour in image_slice.contours})
    primitive_shapes = sorted({primitive.shape for image_slice in slices for primitive in image_slice.primitives})

    meta = dict(header)
    meta.update(
        {
            "filename": str(path),
            "dimensions": dimensions,
            "position": position,
            "offset": (0, 0, 0),
            "origin": origin,
            "vtkbone_origin": tuple(origin[index] + spacing[index] / 2.0 for index in range(3)),
            "direction": IDENTITY_DIRECTION_3D,
            "slice_count": len(slices),
            "contour_count": sum(len(image_slice.contours) for image_slice in slices),
            "primitive_count": sum(len(image_slice.primitives) for image_slice in slices),
            "materials": materials,
            "primitive_shapes": primitive_shapes,
            "rasterization": {
                "chain_code": "3bit_little_endian",
                "axis_mapping": "swap_xy_after_chain_decode",
                "additive_contours": "filled_contour_including_boundary",
                "subtractive_contours": "strict_interior",
                "primitive_shape_4": "rectangle",
                "primitive_shape_6": "ellipse",
                "crop": crop,
                "output_value": int(value),
            },
            "unit": "native",
            "contours": [
                {
                    "material": contour.material,
                    "z": contour.z,
                    "width": contour.width,
                    "height": contour.height,
                    "step_count": contour.step_count,
                    "byte_count": contour.byte_count,
                    "file_offset": contour.file_offset,
                }
                for image_slice in slices
                for contour in image_slice.contours
            ],
            "primitives": [
                {
                    "shape": primitive.shape,
                    "z": primitive.z,
                    "width": primitive.width,
                    "height": primitive.height,
                    "file_offset": primitive.file_offset,
                }
                for image_slice in slices
                for primitive in image_slice.primitives
            ],
        }
    )
    return meta


def gobj_info(path: str | Path) -> dict:
    """Read GOBJ contour-mask metadata without rasterizing the mask."""
    data = Path(path).read_bytes()
    header = _parse_header(data)
    slices = _parse_slices(data, int(header["data_offset"]))
    return _build_meta(path, header, slices)


def read_gobj(path: str | Path, value: int = DEFAULT_MASK_VALUE, crop: str = "tight") -> tuple[np.ndarray, dict]:
    """Read a Scanco GOBJ contour mask as a binary uint8 volume."""
    _validate_raster_options(crop, value)
    data = Path(path).read_bytes()
    header = _parse_header(data)
    slices = _parse_slices(data, int(header["data_offset"]))
    meta = _build_meta(path, header, slices, crop=crop, value=value)
    payload_data = data[int(header["data_offset"]) :]

    width, height, depth = meta["dimensions"]
    position = tuple(meta["position"])
    image = np.zeros((depth, height, width), dtype=np.uint8)
    for image_slice in slices:
        z = image_slice.z - position[2]
        for index, drawable in enumerate(image_slice.drawables):
            if isinstance(drawable, _GobjContour):
                points = _decode_contour_points(payload_data, drawable, position)
                mask = _rasterize_filled_contour((height, width), points)
            else:
                mask = _rasterize_primitive((height, width), drawable, position)
            if _is_subtractive_drawable(drawable, image_slice, index):
                image[z][_strict_interior(mask)] = 0
            else:
                image[z][mask] = int(value)

    return image, meta
