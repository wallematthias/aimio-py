from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

project = "py-aimio"
author = "Matthias Walle"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns: list[str] = []

html_theme = "alabaster"

autodoc_mock_imports = ["py_aimio._aimio"]
autodoc_member_order = "bysource"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
