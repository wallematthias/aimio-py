# aimio-py

[![Coverage (CI)](https://img.shields.io/github/actions/workflow/status/wallematthias/aimio-py/tests.yml?label=coverage%20(ci))](https://github.com/wallematthias/aimio-py/actions/workflows/tests.yml)
[![Wheel Build](https://img.shields.io/github/actions/workflow/status/wallematthias/aimio-py/build-wheels.yml?label=wheels)](https://github.com/wallematthias/aimio-py/actions/workflows/build-wheels.yml)
[![PyPI](https://img.shields.io/pypi/v/aimio-py)](https://pypi.org/project/aimio-py/)

Python bindings for the [Numerics88 AimIO](https://github.com/Numerics88/AimIO) C++ library.

`aimio-py` provides a small Python API to read and write AIM files as NumPy arrays, read ISQ, SCV, and GOBJ files, inspect metadata, and work with processing logs.

## Features

- Read AIM files into NumPy arrays
- Write AIM files from NumPy arrays
- Read ISQ files into NumPy arrays
- Read SCV scout-view files into NumPy arrays
- Read GOBJ contour masks into binary NumPy volumes
- Read AIM, ISQ, SCV, or GOBJ files with single `read_image` and `image_info` dispatchers
- Read RSQ raw detector projections with optional read-only memory mapping
- Access AIM, ISQ, SCV, GOBJ, and RSQ header metadata (`aim_info`, `isq_info`, `scv_info`, `gobj_info`, `rsq_info`)
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
```

## Reading Options

`read_image()` detects AIM, ISQ, SCV, GOBJ, and RSQ files from the extension and
forwards any extra keyword arguments to the format-specific reader.

```python
aim, aim_meta = read_image("scan.AIM", density=True)
isq, isq_meta = read_image("scan.ISQ", unit="density")
scout, scout_meta = read_image("scout.SCV")
mask, mask_meta = read_image("mask.GOBJ", value=1, crop="tight")
counts, rsq_meta = read_image("projections.RSQ", mmap=True)
```

The format-specific readers are also available directly:

- AIM: `read_aim(path, density=False, hu=False)`
- ISQ: `read_isq(path, unit="native")`, where `unit` can be `"native"`, `"hu"`, `"density"`, or `"bmd"`
- SCV: `read_scv(path)`
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
- `read_gobj(path, value=127, crop="tight") -> (array, meta)`
- `read_rsq(path, *, mmap=False) -> (counts, meta)`
- `aim_info(path)`, `isq_info(path)`, `scv_info(path)`, `gobj_info(path)`, `rsq_info(path)`
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

Both readers validate positive dimensions and require an exact payload length
of `2 * product(shape)` bytes after offset `512 * (header_words[127] + 1)`.
Unsupported magic, truncated data, and trailing payload bytes are rejected.
`rsq_info()` checks file size and reads only the base header and final 512-byte
header block. When that block contains a recognized `Beamhard.Corr.` title,
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
