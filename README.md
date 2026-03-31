# py-aimio

[![Coverage (CI)](https://img.shields.io/github/actions/workflow/status/wallematthias/aimio-py/tests.yml?label=coverage%20(ci))](https://github.com/wallematthias/aimio-py/actions/workflows/tests.yml)
[![Wheel Build](https://img.shields.io/github/actions/workflow/status/wallematthias/aimio-py/build-wheels.yml?label=wheels)](https://github.com/wallematthias/aimio-py/actions/workflows/build-wheels.yml)
[![PyPI](https://img.shields.io/pypi/v/py-aimio)](https://pypi.org/project/py-aimio/)

Python bindings for the [Numerics88 AimIO](https://github.com/Numerics88/AimIO) C++ library.

`py-aimio` provides a small Python API to read and write AIM files as NumPy arrays, inspect metadata, and work with processing logs.

## Features

- Read AIM files into NumPy arrays
- Write AIM files from NumPy arrays
- Access AIM header metadata (`aim_info`)
- Convert processing logs between text and dictionary formats
- Optional density/HU conversion helpers

## Installation

From PyPI (recommended):

```bash
pip install py-aimio
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
from py_aimio import read_aim, write_aim

array, meta = read_aim("scan.AIM")
write_aim("copy.AIM", array, meta)
```

## API

- `aim_info(path)`
- `read_aim(path, density=False, hu=False) -> (array, meta)`
- `write_aim(path, array, meta=None, unit=None)`
- `get_aim_density_equation(processing_log)`
- `get_aim_hu_equation(processing_log)`
- `log_to_dict(log)`
- `dict_to_log(dct)`

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

## Release and PyPI Publishing

Wheels and sdist are built by GitHub Actions on:

- `pull_request` to `main`/`master`
- pushes to `main`/`master`
- tags matching `v*`

When a `v*` tag is pushed, the workflow publishes to PyPI via trusted publishing (`pypa/gh-action-pypi-publish`).

See [`docs/PUBLISHING.md`](docs/PUBLISHING.md) for the release checklist and `docs/source/` for Sphinx documentation sources.

## Attribution

- `py_aimio/calibration.py` is adapted from [Bonelab/Bonelab](https://github.com/Bonelab/Bonelab/).
- `py_aimio/header_log.py` is by Matthias Walle.

## License

MIT
