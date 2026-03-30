# py-aimio (local)

This repository provides packaging scaffolding to build Python bindings for the Numerics88 AimIO C++ library.

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
