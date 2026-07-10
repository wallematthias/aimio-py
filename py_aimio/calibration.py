"""
Calibration helpers for converting AIM native values.

These utilities parse AIM processing logs and return linear conversion
equations for HU and density spaces.

Adapted from Bonelab/Bonelab (https://github.com/Bonelab/Bonelab/).
"""

import re
import struct


def _extract(pattern, processing_log, cast, field_name):
    match = re.search(pattern, processing_log)
    if not match:
        raise ValueError(f"Missing calibration field in processing_log: {field_name}")
    return cast(match.group(1))


def get_aim_hu_equation(processing_log):
    """Return linear equation converting native values to HU as ``(m, b)``.

    Use as ``hu = native * m + b``.
    """
    mu_scaling, hu_mu_water, hu_mu_air, _, _ = get_aim_calibration_constants_from_processing_log(processing_log)
    m = 1000.0 / (mu_scaling * (hu_mu_water - hu_mu_air))
    b = -1000.0 * hu_mu_water / (hu_mu_water - hu_mu_air)
    return m, b


def get_aim_density_equation(processing_log):
    """Return linear equation converting native values to density as ``(m, b)``.

    Use as ``density = native * m + b``.
    """
    mu_scaling, _, _, density_slope, density_intercept = get_aim_calibration_constants_from_processing_log(processing_log)
    m = density_slope / mu_scaling
    b = density_intercept
    return m, b


def get_aim_calibration_constants_from_processing_log(processing_log):
    """Extract calibration constants from an AIM processing log string.

    Returns:
        Tuple ``(mu_scaling, hu_mu_water, hu_mu_air, density_slope, density_intercept)``.

    Throws:
        ValueError if constants not present in processing log
    """
    number = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"

    mu_scaling = _extract(r"Mu_Scaling\s+(\d+)", processing_log, int, "Mu_Scaling")
    hu_mu_water = _extract(r"HU:\s*mu water\s+" + number, processing_log, float, "HU: mu water")
    hu_mu_air = 0
    density_slope = _extract(r"Density:\s*slope\s+" + number, processing_log, float, "Density: slope")
    density_intercept = _extract(r"Density:\s*intercept\s+" + number, processing_log, float, "Density: intercept")

    return mu_scaling, hu_mu_water, hu_mu_air, density_slope, density_intercept


def decode_scanco_double(data):
    """Decode a Scanco/VMS-style double from an 8-byte buffer."""
    if len(data) != 8:
        raise ValueError("Scanco double data must be exactly 8 bytes")
    high = (data[0] << 16) | (data[1] << 24) | data[2] | (data[3] << 8)
    low = (data[4] << 16) | (data[5] << 24) | data[6] | (data[7] << 8)
    bits = ((high & 0xFFFFFFFF) << 32) | (low & 0xFFFFFFFF)
    return struct.unpack("<d", struct.pack("<Q", bits))[0] * 0.25


def get_isq_hu_equation(meta):
    """Return linear equation converting ISQ native values to HU as ``(m, b)``."""
    mu_scaling = meta.get("mu_scaling")
    mu_water = meta.get("mu_water")
    if mu_scaling is None or mu_water is None:
        raise ValueError("ISQ calibration metadata is required for HU conversion")
    if float(mu_scaling) <= 1.0 or float(mu_water) <= 0.0:
        raise ValueError("ISQ calibration metadata contains invalid HU constants")
    return 1000.0 / (float(mu_scaling) * float(mu_water)), -1000.0


def get_isq_density_equation(meta):
    """Return linear equation converting ISQ native values to density/BMD as ``(m, b)``."""
    slope = meta.get("rescale_slope")
    intercept = meta.get("rescale_intercept")
    if slope is None or intercept is None:
        raise ValueError("ISQ calibration metadata is required for density conversion")
    return float(slope), float(intercept)
