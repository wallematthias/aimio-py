# Changelog

## 0.4.0 — 2026-10-03

- Read supported RSQ raw detector projections with `read_rsq` and `rsq_info`, including read-only memory mapping and VMS filename versions.
- Validate storage dimensions, exact payload length, and recognized beam-hardening calibration against header anchors.
- Add RSQ dispatch to `read_image`, `image_info`, their aliases, and `aimio-info`.
- Document projection axis order and the limits of inferred geometry and unsigned-count interpretation. Existing reconstructed-image readers retain their behavior.

The version advances beyond existing repository tags through 0.3.0. The previous public PyPI release was 0.1.9.
