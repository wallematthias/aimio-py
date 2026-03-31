"""
Calibration helpers for converting AIM native values.

These utilities parse AIM processing logs and return linear conversion
equations for HU and density spaces.

Adapted from Bonelab/Bonelab (https://github.com/Bonelab/Bonelab/).
"""

import re


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
    """
    number = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"

    mu_scaling = _extract(r"Mu_Scaling\s+(\d+)", processing_log, int, "Mu_Scaling")
    hu_mu_water = _extract(r"HU:\s*mu water\s+" + number, processing_log, float, "HU: mu water")
    hu_mu_air = 0
    density_slope = _extract(r"Density:\s*slope\s+" + number, processing_log, float, "Density: slope")
    density_intercept = _extract(r"Density:\s*intercept\s+" + number, processing_log, float, "Density: intercept")

    return mu_scaling, hu_mu_water, hu_mu_air, density_slope, density_intercept
