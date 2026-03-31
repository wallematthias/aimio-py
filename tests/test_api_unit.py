import numpy as np
import pytest

import py_aimio as api


PROCESSING_LOG = """Mu_Scaling                    1000
HU: mu water                  1.0
Density: slope                2.0
Density: intercept            3.0
"""


class DummyAimio:
    def __init__(self):
        self.last_write = None

    def aim_info(self, path):
        return {"path": path, "dimensions": (2, 2, 2)}

    def read_aim(self, _path):
        arr = np.array([[[0, 1000]]], dtype=np.int16)
        return arr, {"processing_log": PROCESSING_LOG}

    def write_aim(self, path, arr, meta):
        self.last_write = (path, arr, meta)
        return {"path": path, "shape": tuple(arr.shape)}


def test_aim_info_calls_backend(monkeypatch):
    backend = DummyAimio()
    monkeypatch.setattr(api, "_aimio", backend)
    info = api.aim_info("x.AIM")
    assert info["path"] == "x.AIM"


def test_not_built_paths_raise(monkeypatch):
    monkeypatch.setattr(api, "_aimio", None)
    with pytest.raises(RuntimeError):
        api.aim_info("x.AIM")
    with pytest.raises(RuntimeError):
        api.read_aim("x.AIM")
    with pytest.raises(RuntimeError):
        api.write_aim("x.AIM", np.zeros((1, 1, 1), dtype=np.int16))


def test_read_aim_mutually_exclusive_conversion_flags(monkeypatch):
    monkeypatch.setattr(api, "_aimio", DummyAimio())
    with pytest.raises(ValueError, match="Use only one conversion option"):
        api.read_aim("x.AIM", density=True, hu=True)


def test_read_aim_density_conversion(monkeypatch):
    monkeypatch.setattr(api, "_aimio", DummyAimio())
    arr, meta = api.read_aim("x.AIM", density=True)
    assert np.allclose(arr, np.array([[[3.0, 5.0]]]))
    assert meta["unit"] == "BMD"
    assert isinstance(meta["processing_log"], dict)
    assert isinstance(meta["processing_log_raw"], str)


def test_read_aim_hu_conversion(monkeypatch):
    monkeypatch.setattr(api, "_aimio", DummyAimio())
    arr, meta = api.read_aim("x.AIM", hu=True)
    assert np.allclose(arr, np.array([[[-1000.0, 0.0]]]))
    assert meta["unit"] == "HU"


def test_read_aim_keeps_processing_log_string_when_parse_fails(monkeypatch):
    monkeypatch.setattr(api, "_aimio", DummyAimio())

    def _boom(_):
        raise ValueError("parse failed")

    monkeypatch.setattr(api, "log_to_dict", _boom)
    arr, meta = api.read_aim("x.AIM")
    assert arr.shape == (1, 1, 2)
    assert isinstance(meta["processing_log"], str)
    assert isinstance(meta["processing_log_raw"], str)


def test_write_aim_native_path(monkeypatch):
    backend = DummyAimio()
    monkeypatch.setattr(api, "_aimio", backend)

    arr = np.array([[[1, 2]]], dtype=np.int16)
    result = api.write_aim("out.AIM", arr, meta={"unit": "native"})
    assert result["path"] == "out.AIM"
    _, written_arr, written_meta = backend.last_write
    assert np.array_equal(written_arr, arr)
    assert written_arr.flags["C_CONTIGUOUS"]
    assert written_meta["unit"] == "native"


def test_write_aim_density_with_dict_processing_log(monkeypatch):
    backend = DummyAimio()
    monkeypatch.setattr(api, "_aimio", backend)

    proc_dict = api.log_to_dict(PROCESSING_LOG)
    arr_density = np.array([[[3.0, 5.0]]], dtype=np.float32)
    api.write_aim("out.AIM", arr_density, meta={"unit": "BMD", "processing_log": proc_dict})
    _, written_arr, written_meta = backend.last_write
    assert np.allclose(written_arr, np.array([[[0.0, 1000.0]]]))
    assert isinstance(written_meta["processing_log"], str)


def test_write_aim_hu_with_unit_override(monkeypatch):
    backend = DummyAimio()
    monkeypatch.setattr(api, "_aimio", backend)

    arr_hu = np.array([[[-1000.0, 0.0]]], dtype=np.float32)
    api.write_aim("out.AIM", arr_hu, meta={"processing_log": PROCESSING_LOG}, unit="HU")
    _, written_arr, _ = backend.last_write
    assert np.allclose(written_arr, np.array([[[0.0, 1000.0]]]))
