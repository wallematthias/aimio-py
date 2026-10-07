# aimio-py

[![Coverage (CI)](https://img.shields.io/github/actions/workflow/status/wallematthias/aimio-py/tests.yml?label=coverage%20(ci))](https://github.com/wallematthias/aimio-py/actions/workflows/tests.yml)
[![Wheel Build](https://img.shields.io/github/actions/workflow/status/wallematthias/aimio-py/build-wheels.yml?label=wheels)](https://github.com/wallematthias/aimio-py/actions/workflows/build-wheels.yml)
[![PyPI](https://img.shields.io/pypi/v/aimio-py)](https://pypi.org/project/aimio-py/)

Python bindings for the [Numerics88 AimIO](https://github.com/Numerics88/AimIO) C++ library.

`aimio-py` provides a small Python API to read and write AIM files as NumPy arrays, read ISQ, SCV, GOBJ, RAD, and RSQ files, inspect metadata, and work with processing logs.

## Features

- Read AIM files into NumPy arrays
- Write AIM files from NumPy arrays
- Read ISQ files into NumPy arrays
- Read SCV scout-view files into NumPy arrays
- Read native RAD radiographs with header-derived mm spacing
- Read GOBJ contour masks into binary NumPy volumes
- Read AIM, ISQ, SCV, GOBJ, RAD, or RSQ files with single `read_image` and `image_info` dispatchers
- Read RSQ raw detector projections with optional read-only memory mapping
- Access format-specific header metadata (`aim_info`, `isq_info`, `scv_info`, `gobj_info`, `rad_info`, `rsq_info`)
- Convert processing logs between text and dictionary formats
- Optional density/HU conversion helpers

## Installation

From PyPI (recommended):

```bash
pip install aimio-py
```

From source:

```bash
git clone https://github.com/wallematthias/aimio-py.git
cd aimio-py
git submodule update --init --recursive
pip install -e .
```

## Quickstart

```python
from py_aimio import image_info, read_image, write_aim

array, meta = read_image("scan.AIM")
print(meta["origin"], meta["spacing"], meta["direction"])

header = image_info("scan.AIM")
write_aim("copy.AIM", array, meta)
```

The matching metadata CLI uses the same format resolution:

```bash
aimio-info scan.AIM
aimio-info mask.GOBJ --format gobj
aimio-info projections.RSQ --format rsq
aimio-info scout.RAD --format rad
```

## Reading Options

`read_image()` detects AIM, ISQ, SCV, GOBJ, RAD, and RSQ files from the extension and
forwards any extra keyword arguments to the format-specific reader.

```python
aim, aim_meta = read_image("scan.AIM", density=True)
isq, isq_meta = read_image("scan.ISQ", unit="density")
scout, scout_meta = read_image("scout.SCV")
radiograph, rad_meta = read_image("scout.RAD")
mask, mask_meta = read_image("mask.GOBJ", value=1, crop="tight")
counts, rsq_meta = read_image("projections.RSQ", mmap=True)
```

The format-specific readers are also available directly:

- AIM: `read_aim(path, density=False, hu=False)`
- ISQ: `read_isq(path, unit="native")`, where `unit` can be `"native"`, `"hu"`, `"density"`, or `"bmd"`
- SCV: `read_scv(path)`
- RAD: `read_rad(path)`
- GOBJ: `read_gobj(path, value=127, crop="tight")`, where `crop` can be `"tight"` or `"header"`
- RSQ: `read_rsq(path, *, mmap=False)`

At the moment, AIM and ISQ default to native stored values. For calibrated bone
workflows, request density/BMD explicitly with `density=True` for AIM or
`unit="density"`/`unit="bmd"` for ISQ.

## API

- `read_image(path, format="auto", **kwargs) -> (array, meta)`
- `image_info(path, format="auto") -> meta`

Format-specific readers and metadata helpers are also available:

- `read_aim(path, density=False, hu=False) -> (array, meta)`
- `read_isq(path, unit="native") -> (array, meta)`
- `read_scv(path) -> (array, meta)`
- `read_rad(path) -> (array, meta)`
- `read_gobj(path, value=127, crop="tight") -> (array, meta)`
- `read_rsq(path, *, mmap=False) -> (counts, meta)`
- `aim_info(path)`, `isq_info(path)`, `scv_info(path)`, `gobj_info(path)`, `rad_info(path)`, `rsq_info(path)`
- `write_aim(path, array, meta=None, unit=None)`
- `get_aim_density_equation(processing_log)`
- `get_aim_hu_equation(processing_log)`
- `log_to_dict(log)`
- `dict_to_log(dct)`

Read metadata includes SimpleITK-style geometry keys for both AIM and ISQ:
`origin`, `spacing`, and `direction`. For AIM, `spacing` is copied from
`element_size` and `origin` follows the ITKIOScanco-compatible convention:
`(position + offset) * spacing`. The older vtkbone-style half-voxel-shifted
origin is also exposed as `vtkbone_origin`. For ISQ, `spacing` comes from the ISQ
header and `origin` defaults to `(0.0, 0.0, 0.0)`. `direction` currently defaults
to the 3D identity direction, matching the practical behavior observed from
ITKIOScanco for ISQ files without explicit orientation metadata.

GOBJ files are read as contour masks. Additive contours are rasterized as
filled contours including their boundary. Subtractive contours, such as inner
cortical boundaries, remove only the strict contour interior so the contour
boundary remains part of the mask. `crop="tight"` returns the contour bounding
box, while `crop="header"` returns the full CTDATA header grid.

SCV scout readers accept both stream exports and binary extracts that retain
VMS variable-length record wrappers. RMS length words and odd-record alignment
bytes are skipped in memory; the source file is never rewritten. Outer record
lengths must match the enclosed SCV profiles. Metadata reports `storage_format`
(`stream` or `vms_variable_records`), and record/payload offsets refer to the
original file, including any wrappers.

SCV profile records contain a two-byte marker, a VMS F-floating row coordinate,
a compressed-byte count, and the **complete** run-length-encoded pixel row.
The first two compressed bytes are pixels, not a separate horizontal offset.
Each decoded row must match the declared width; truncated runs and excess
records are rejected. The `aux` and `phase` fields remain raw compatibility
metadata, not geometry parameters.

The historical SCV `spacing`/`origin` convention matches IPL's `scv_to_aim`
output for the paired reference scout. This does not establish calibrated
physical geometry for every scanner variant: scouts with repeated/nonuniform
row coordinates or invalid extents load with unit spacing and zero origin in
**pixel space**, with a warning. `geometry_unit`, `geometry_source`, and
`geometry_warning` identify this fallback; `row_positions_mm` and
`header_spacing` retain the original information. Do not use pixel-space scouts
for physical measurements or registration. Stripping VMS wrappers alone does
not repair such geometry.

## RAD radiographs

`read_rad(path)` returns a native signed-int16 **2D** array in `(row, column)`
order; `rad_info(path)` inspects the header and validates storage without loading
pixels. The pure-Python reader supports `CTDATA-HEADER_V1`, type-9 radiographs,
including extra header blocks and optional zero padding to the next 512-byte
boundary. The source file is never rewritten.

RAD physical dimensions are **nanometres**, unlike ISQ's micrometres. Metadata
converts them to mm in `physical_dimensions_mm`, `spacing`, and `element_size`;
`dimensions` is `(width, height, 1)`, and the placeholder third-axis spacing is
1 mm, not a measured slice thickness. `origin=(0,0,0)` and identity direction
describe a standalone display plane, **not co-registration with CT**.
`z_position_mm`, `reference_line_mm`, and scan start/end positions are retained
separately. No HU/density conversion is supported for this projection image.

Header interpretation follows the RAD branch of
[David Gobbi's vtk-dicom Scanco reader](https://github.com/dgobbi/vtk-dicom/blob/master/Source/vtkScancoCTReader.cxx).

## RSQ raw projections

```python
from py_aimio import read_rsq, rsq_info

counts, meta = read_rsq("projections.RSQ;1", mmap=True)
print(counts.shape, meta["axis_order"])
header = rsq_info("projections.RSQ;1")
```

The supported RSQ storage interpretation uses the 16-byte
`CTDATA-HEADER_V1` magic and 128 little-endian unsigned header words. Arrays
have shape `(header_words[13], header_words[12], header_words[11])` and axes
`("detector_row", "frame", "detector_column")`. Values are decoded as
little-endian unsigned 16-bit detector counts (`<u2`), preserving values up to
65535. Signedness has not been independently confirmed for every proprietary
Scanco RSQ variant. `mmap=True` returns a read-only NumPy memory map.

Every stored frame is retained. Object views and any reference frames are not
classified or discarded, and raw reading does not require a minimum number of
frames. RSQ projections do not carry reconstructed volume `origin`, `spacing`,
or `direction` keys. Spatial volume, HU, and density conversion requests through
`read_image()` raise `ValueError`.

Metadata includes `header_words`, `shape`, `axis_order`, `dtype`,
`data_offset_bytes`, and a `geometry` dictionary with explicit provenance and
header positions. Geometry hints include requested output pitch and axial start
in micrometers, native detector dimensions, detector size, source distances,
binning, object view count, and angular interval in millidegrees. These are
partially inferred header meanings, not independently validated reconstruction
geometry. Words 21 and 22 are exposed as `count_range`; they do not define
attenuation scaling. Patient-name fields are not decoded, although raw header
words can still contain identifying data.

Both readers validate positive dimensions and require a detector payload length
of `2 * product(shape)` bytes after offset `512 * (header_words[127] + 1)`.
An optional zero-filled tail extending exactly to the next 512-byte boundary
is accepted for VMS block-aligned extracts and reported as `padding_size_bytes`.
Unsupported magic, truncated data, nonzero padding, and other trailing bytes
are rejected. `rsq_info()` checks file size and reads only the base header,
final 512-byte header block, and any padding, not detector counts.
When that block contains a recognized `Beamhard.Corr.` title,
three float64 coefficients at bytes 476:500 are checked against the printed
`Corr at 2 3 6:` anchors using
`delta(p) = a1*p + a2*p**2 + a3*p**3` with absolute tolerance `1e-6`.
Corrupt recognized calibration raises `ValueError`; absent or unrecognized
calibration has `beam_hardening["available"] = False`. The reader exposes
validated coefficients without applying them to counts.

## Development

Run tests:

```bash
pytest -q
```

Run tests with coverage:

```bash
pytest -q --cov=py_aimio --cov-report=term-missing --cov-report=xml:coverage.xml
```

Build local artifacts:

```bash
python -m build --wheel --sdist
```

Build documentation from docstrings:

```bash
pip install sphinx
make -C docs html
```

Generated HTML will be in `docs/build/html/index.html`.

### Important build note

This project depends on the `external/AimIO` and `external/n88util` git submodules. If they are missing, extension builds will fail.

## Attribution

- `py_aimio/calibration.py` is adapted from [Bonelab/Bonelab](https://github.com/Bonelab/Bonelab/).
- `py_aimio/header_log.py` is by Matthias Walle.
- `py_aimio/scv.py` and `py_aimio/gobj.py` are by Matthias Walle and Andrew Burghardt.

## License

MIT
