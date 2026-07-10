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
- Access AIM, ISQ, SCV, and GOBJ header metadata (`aim_info`, `isq_info`, `scv_info`, `gobj_info`)
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
from py_aimio import image_info, read_aim, read_gobj, read_image, read_isq, read_scv, write_aim

array, meta = read_aim("scan.AIM")
print(meta["origin"], meta["spacing"], meta["direction"])
write_aim("copy.AIM", array, meta)

isq_array, isq_meta = read_isq("scan.ISQ")
scout_array, scout_meta = read_scv("scout.SCV")
mask_array, mask_meta = read_gobj("mask.GOBJ")

image, image_meta = read_image("scan.ISQ")
header_meta = image_info("mask.GOBJ")
```

The matching metadata CLI uses the same format resolution:

```bash
aimio-info scan.AIM
aimio-info mask.GOBJ --format gobj
```

## Reading ISQ files

```python
from py_aimio import isq_info, read_isq

info = isq_info("scan.ISQ")
print("Dimensions:", info["dimensions"])
print("Voxel spacing:", info["spacing"])

array, meta = read_isq("scan.ISQ")
print(array.shape, array.dtype)  # (z, y, x), int16

hu_array, hu_meta = read_isq("scan.ISQ", unit="hu")
bmd_array, bmd_meta = read_isq("scan.ISQ", unit="density")
```

## API

- `aim_info(path)`
- `gobj_info(path)`
- `isq_info(path)`
- `scv_info(path)`
- `image_info(path, format="auto") -> meta`
- `read_image(path, format="auto", **kwargs) -> (array, meta)`
- `read_aim(path, density=False, hu=False) -> (array, meta)`
- `read_gobj(path, value=127, crop="tight") -> (array, meta)`
- `read_isq(path, unit="native") -> (array, meta)`
- `read_scv(path) -> (array, meta)`
- `write_aim(path, array, meta=None, unit=None)`
- `get_aim_density_equation(processing_log)`
- `get_aim_hu_equation(processing_log)`
- `log_to_dict(log)`
- `dict_to_log(dct)`

For ISQ files, `unit="native"` returns stored scanner values. `unit="hu"` and
`unit="density"`/`unit="bmd"` use calibration metadata from the ISQ extended
header when present.

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

## License

MIT
