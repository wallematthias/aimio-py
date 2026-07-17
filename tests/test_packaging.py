import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_build_numpy_requirement_remains_compatible_with_cp310_wheels():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    build_requires = pyproject["build-system"]["requires"]

    numpy_requires = [req for req in build_requires if req.startswith("numpy")]

    assert any("python_version < '3.11'" in req and "<2.3" in req for req in numpy_requires)
    assert any("python_version >= '3.11'" in req for req in numpy_requires)
