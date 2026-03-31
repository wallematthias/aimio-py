# Publishing Checklist

## One-time setup

1. Enable trusted publishing on PyPI for this GitHub repository.
2. In GitHub, ensure the workflow can access the `pypi` environment.
3. Confirm `external/AimIO` and `external/n88util` submodules are committed and accessible.

## Pre-release checks

1. Update version in `setup.cfg`.
2. Run local tests:
   ```bash
   pytest -q
   ```
3. Run a local build:
   ```bash
   python -m build --wheel --sdist
   ```
4. Verify metadata:
   ```bash
   python -m pip install twine
   twine check dist/*
   ```

## Release steps

1. Commit all release changes to `main`.
2. Create and push a version tag:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
3. Monitor `.github/workflows/build-wheels.yml` for:
   - wheel build on Linux/macOS/Windows
   - sdist build
   - PyPI publish step success

## Post-release checks

1. Confirm package is visible on PyPI.
2. Validate installation in a clean environment:
   ```bash
   pip install aimio-py==0.1.0
   ```
