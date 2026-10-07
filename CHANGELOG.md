# Changelog

## Unreleased

## 0.4.1 — 2026-10-07

- Add pure-Python `read_rad`/`rad_info` for type-9 CTDATA scout radiographs, preserving signed int16 values and converting nanometre header dimensions to mm. Support RAD in image dispatch, aliases, and `aimio-info` without HU/density conversion.
- Load SCV scouts with repeated/nonuniform row coordinates or invalid extents in explicitly labelled pixel space, retaining original coordinates and warning against physical measurements.
- Accept zero-filled RSQ padding that extends exactly to the next 512-byte VMS block boundary, while retaining strict payload and corruption checks.
- Read SCV binary extracts containing VMS variable-length record wrappers and alignment bytes without rewriting the source; preserve physical file offsets in metadata.
- Add synthetic regression tests for padded RSQ reads, wrapped SCV scout pixels, and malformed storage records.
- Decode complete SCV RLE rows rather than interpreting their first two bytes as an offset; reject truncated runs and width mismatches.
- Read SCV profile positions as complete VMS F-floating values, correcting the exponent-dependent coordinate error while retaining IPL-compatible reference-scout pixels and geometry.
- Run RAD, SCV, and RSQ regression tests against each built platform wheel.

## 0.4.0 — 2026-10-03

- Read supported RSQ raw detector projections with `read_rsq` and `rsq_info`, including read-only memory mapping and VMS filename versions.
- Validate storage dimensions, exact payload length, and recognized beam-hardening calibration against header anchors.
- Add RSQ dispatch to `read_image`, `image_info`, their aliases, and `aimio-info`.
- Document projection axis order and the limits of inferred geometry and unsigned-count interpretation. Existing reconstructed-image readers retain their behavior.

The version advances beyond existing repository tags through 0.3.0. The previous public PyPI release was 0.1.9.
