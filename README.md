# py-aimio (local)

## Attribution

- `py_aimio/calibration.py` and `py_aimio/converters.py` are adapted from [Bonelab/Bonelab](https://github.com/Bonelab/Bonelab/).
- `py_aimio/header_log.py` is by Matthias Walle.




This repository provides Python bindings for the [Numerics88 AimIO C++ library](https://github.com/Numerics88/AimIO) and uses [n88util](https://github.com/Numerics88/n88util) for utility functions. Please see those upstream repositories for the original C++ code, documentation, and license details.

**Why (local)?**

This is a local, developer-focused version of py-aimio. It is intended for:
- Testing and development before public release or PyPI upload
- Environments where you want to build from source, modify, or debug the bindings
- Users who need to integrate with unreleased or custom versions of AimIO/n88util

For most users, the recommended way is to use the pre-built wheels from the [GitHub Releases page](https://github.com/wallematthias/aimio-py/releases) for easy installation.

**Note:** This repo does not contain the full C++ sources. It is a Python packaging/shim layer. All C++ build artifacts (such as `_aimio.cpython-*.so`) are ignored and should not be committed.

# Pre-built Wheels (Recommended)

For most users, download the latest wheel for your platform from the [GitHub Releases page](https://github.com/wallematthias/aimio-py/releases) and install with pip:

```
pip install https://github.com/wallematthias/aimio-py/releases/download/<TAG>/<WHEEL_FILENAME>.whl
```
Replace `<TAG>` with the latest release tag (e.g., `v1.0.0`) and `<WHEEL_FILENAME>` with the correct file for your OS and Python version.

Quickstart

1. Add AimIO as a git submodule inside this folder:

# py-aimio

Minimal Python bindings for the Numerics88 AIM file format (micro-CT image IO).

- Pure Python + pybind11, minimal dependencies
- Read/write AIM files as numpy arrays
- Extract and edit AIM metadata
- MIT License

## Installation

```sh
pip install py-aimio
```

## Usage

```python
from py_aimio import read_aim, write_aim

arr, meta = read_aim('scan.aim')
# ... process arr ...
write_aim('out.aim', arr, meta)
```

## API
- `read_aim(path, density=False, hu=False) -> (array, meta)`
- `write_aim(path, array, meta=None, unit=None)`
- `aim_info(path)`
- `get_aim_density_equation(processing_log)`
- `get_aim_hu_equation(processing_log)`
- `log_to_dict(log)` / `dict_to_log(dict)`

## License
MIT

---
For advanced usage, see the full documentation or source code.
