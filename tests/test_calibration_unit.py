import math

import pytest

from py_aimio.calibration import (
    get_aim_calibration_constants_from_processing_log,
    get_aim_density_equation,
    get_aim_hu_equation,
)


PROCESSING_LOG = """Mu_Scaling                    1000
HU: mu water                  1.0
Density: slope                2.0
Density: intercept            3.0
"""


def test_parse_calibration_constants():
    mu_scaling, hu_mu_water, hu_mu_air, density_slope, density_intercept = (
        get_aim_calibration_constants_from_processing_log(PROCESSING_LOG)
    )
    assert mu_scaling == 1000
    assert hu_mu_water == 1.0
    assert hu_mu_air == 0
    assert density_slope == 2.0
    assert density_intercept == 3.0


def test_get_aim_hu_equation():
    m, b = get_aim_hu_equation(PROCESSING_LOG)
    assert math.isclose(m, 1.0)
    assert math.isclose(b, -1000.0)


def test_get_aim_density_equation():
    m, b = get_aim_density_equation(PROCESSING_LOG)
    assert math.isclose(m, 0.002)
    assert math.isclose(b, 3.0)


def test_missing_calibration_field_raises():
    with pytest.raises(ValueError, match="Missing calibration field"):
        get_aim_density_equation("HU: mu water 1.0")
