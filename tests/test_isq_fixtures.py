from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import py_aimio as api


DATA_DIR = Path(__file__).resolve().parent / "data"
CALIBRATED_ISQ = DATA_DIR / "test_isq_calibrated_binary_25.ISQ"
NATIVE_ONLY_ISQ = DATA_DIR / "test_isq_native_only_binary_25.ISQ"


def test_calibrated_fixture_reads_native_hu_and_bmd():
    native, native_meta = api.read_isq(str(CALIBRATED_ISQ))
    hu, hu_meta = api.read_isq(str(CALIBRATED_ISQ), unit="hu")
    bmd, bmd_meta = api.read_isq(str(CALIBRATED_ISQ), unit="bmd")

    assert native.shape == (25, 25, 25)
    assert native.dtype == np.int16
    assert np.unique(native).tolist() == [0, 1]
    assert native_meta["unit"] == "native"

    assert np.unique(hu).tolist() == [-1000.0, -999.0]
    assert hu_meta["unit"] == "HU"

    assert np.unique(bmd).tolist() == [3.0, 5.0]
    assert bmd_meta["unit"] == "BMD"
    assert bmd_meta["rescale_units"] == "mg HA/ccm"


def test_native_only_fixture_rejects_calibrated_units():
    native, native_meta = api.read_isq(str(NATIVE_ONLY_ISQ), unit="native")

    assert native.shape == (25, 25, 25)
    assert native.dtype == np.int16
    assert np.unique(native).tolist() == [0, 1]
    assert native_meta["unit"] == "native"
    assert "rescale_slope" not in native_meta
    assert "mu_water" not in native_meta

    with pytest.raises(ValueError, match="ISQ calibration metadata"):
        api.read_isq(str(NATIVE_ONLY_ISQ), unit="hu")

    with pytest.raises(ValueError, match="ISQ calibration metadata"):
        api.read_isq(str(NATIVE_ONLY_ISQ), unit="density")


def test_calibrated_fixture_is_readable_by_itk_ioscanco_when_available():
    itk = pytest.importorskip("itk")

    image = itk.imread(str(CALIBRATED_ISQ))
    itk_array = itk.array_from_image(image)
    aimio_hu, _ = api.read_isq(str(CALIBRATED_ISQ), unit="hu")

    np.testing.assert_array_equal(itk_array, aimio_hu.astype(np.int16))


def test_native_only_fixture_is_readable_by_itk_ioscanco_when_available():
    itk = pytest.importorskip("itk")

    image = itk.imread(str(NATIVE_ONLY_ISQ))
    itk_array = itk.array_from_image(image)
    aimio_native, _ = api.read_isq(str(NATIVE_ONLY_ISQ), unit="native")

    np.testing.assert_array_equal(itk_array, aimio_native)
