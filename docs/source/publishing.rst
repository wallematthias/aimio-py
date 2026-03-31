Publishing
==========

Pre-release checklist:

1. Update the version in ``setup.cfg``.
2. Run tests: ``pytest -q``.
3. Build package artifacts: ``python -m build --wheel --sdist``.
4. Validate metadata: ``twine check dist/*``.

Release:

1. Tag and push a release, for example ``v0.1.1``.
2. GitHub Actions builds wheels/sdist and publishes on tag pushes.

For the full workflow details, see ``docs/PUBLISHING.md`` in the repository.
