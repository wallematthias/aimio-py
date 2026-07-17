from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_build_numpy_requirement_remains_compatible_with_cp310_wheels():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"numpy>=1.20,<2.3; python_version < \'3.11\'"' in pyproject
    assert '"numpy>=1.20; python_version >= \'3.11\'"' in pyproject
