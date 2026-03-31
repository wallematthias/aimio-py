# py-aimio (local)


This repository provides Python bindings for the [Numerics88 AimIO C++ library](https://github.com/Numerics88/AimIO) and uses [n88util](https://github.com/Numerics88/n88util) for utility functions. Please see those upstream repositories for the original C++ code, documentation, and license details.

**Note:** This repo does not contain the full C++ sources. It is a Python packaging/shim layer. All C++ build artifacts (such as `_aimio.cpython-*.so`) are ignored and should not be committed.

# Pre-built Wheels (Recommended)

For most users, download the latest wheel for your platform from the [GitHub Releases page](https://github.com/wallematthias/aimio-py/releases) and install with pip:

```
pip install https://github.com/wallematthias/aimio-py/releases/download/<TAG>/<WHEEL_FILENAME>.whl
```
Replace `<TAG>` with the latest release tag (e.g., `v1.0.0`) and `<WHEEL_FILENAME>` with the correct file for your OS and Python version.

Quickstart

1. Add AimIO as a git submodule inside this folder:

```sh
cd active/aimio-py
git submodule add https://github.com/Numerics88/AimIO AimIO
git submodule update --init --recursive
```

2. Build/install locally (recommended in a virtualenv):

```sh
2. Build/install locally (recommended in a conda environment):

```bash
cd active/aimio-py
# add AimIO submodule if not already added
git submodule add https://github.com/Numerics88/AimIO AimIO || true
git submodule update --init --recursive

# create conda env and install deps (conda-forge)
conda create -n aimio-build -c conda-forge python=3.11 boost pybind11 numpy pip build setuptools wheel cmake -y
conda activate aimio-build

# build and install editable
pip install -U pip
pip install -e .
```

pip install -U pip setuptools wheel
pip install -e .
```

Notes
- The build uses pybind11 and numpy at build time. They are declared in `pyproject.toml`.
- The C++ sources from AimIO will be discovered under `AimIO/source` and headers under `AimIO/include`.
- `bindings/aimio_bindings.cpp` is a minimal placeholder; extend it to wrap useful AimIO APIs.
